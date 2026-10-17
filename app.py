import json
import copy
import re
import os
import secrets
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from flask import (
    Flask,
    Response,
    abort,
    jsonify,
    render_template,
    request,
    session,
    stream_with_context,
)
from dotenv import load_dotenv
from engine import extract, build, reply
from providers import gemini_stream, gemini_plan, fred_data
from conversation import resolve as resolve_workspace, SYMBOL, workspace_reply

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")
app = Flask(__name__)
app.config.update(
    MAX_CONTENT_LENGTH=32000,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE") == "1",
)
data_dir = Path(os.getenv("FOLIO_DATA_DIR", str(ROOT / "instance")))
data_dir.mkdir(parents=True, exist_ok=True)
secret = data_dir / "secret.key"
if not secret.exists():
    try:
        fd = os.open(secret, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(secrets.token_hex(32))
    except FileExistsError:
        pass
app.secret_key = os.getenv("SECRET_KEY") or secret.read_text()
DB = data_dir / "folio.sqlite3"
with sqlite3.connect(DB) as c:
    c.execute(
        "CREATE TABLE IF NOT EXISTS conversations (id TEXT PRIMARY KEY, data TEXT NOT NULL)"
    )
locks = {}
locks_guard = threading.Lock()


def identity():
    if "id" not in session:
        session["id"] = secrets.token_urlsafe(24)
    session.permanent = True
    return session["id"]


def read(cid):
    from localization import normalize_profile

    with sqlite3.connect(DB) as c:
        row = c.execute("SELECT data FROM conversations WHERE id=?", (cid,)).fetchone()
    state = (
        json.loads(row[0])
        if row
        else dict(profile={}, messages=[], portfolio=None, version=0)
    )
    state["profile"] = normalize_profile(state.get("profile", {}))
    if state.get("portfolio"):
        state["portfolio"]["profile"] = normalize_profile(
            state["portfolio"].get("profile", {})
        )
    return state


def save(cid, state):
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB) as c:
        c.execute(
            "INSERT OR REPLACE INTO conversations VALUES (?,?)",
            (cid, json.dumps(state, ensure_ascii=False)),
        )


def lock_for(cid):
    with locks_guard:
        return locks.setdefault(cid, threading.Lock())


@app.before_request
def csrf():
    identity()
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(24)
    if (
        request.method in ("POST", "DELETE", "PUT")
        and request.headers.get("X-CSRF-Token") != session["csrf"]
    ):
        abort(403)


@app.url_defaults
def static_asset_version(endpoint, values):
    if endpoint == "static" and "filename" in values and "v" not in values:
        asset = ROOT / "static" / values["filename"]
        if asset.is_file():
            values["v"] = str(asset.stat().st_mtime_ns)


@app.after_request
def headers(res):
    res.headers["X-Content-Type-Options"] = "nosniff"
    res.headers["Referrer-Policy"] = "same-origin"
    res.headers["X-Frame-Options"] = "DENY"
    if request.path.startswith("/api/") or res.mimetype == "text/html":
        res.headers["Cache-Control"] = "no-store"
    return res


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/state")
def state():
    payload = read(identity())
    if not payload.get("workspace") and payload.get("messages"):
        context = {}
        for message in payload["messages"]:
            if message["role"] == "user":
                context = resolve_workspace(message["text"], context)
        payload["workspace"] = {**context, "version": payload["version"]}
    return jsonify(
        **payload,
        csrf=session["csrf"],
        provider="Gemini" if os.getenv("GEMINI_API_KEY") else "Local allocation engine",
        fred=bool(os.getenv("FRED_API_KEY")),
    )


@app.post("/api/chat")
def chat():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify(error="Request must be a  JSON  object"), 400
    text = body.get("message")
    if not isinstance(text, str) or not text.strip() or len(text) > 4000:
        return jsonify(error="Enter  1–4000  characters describing your investment idea"), 400
    cid = identity()
    lock = lock_for(cid)
    if not lock.acquire(blocking=False):
        return jsonify(error="The previous response is still generating. Please wait."), 409

    def event(kind, data):
        return (
            "event: "
            + kind
            + "\ndata: "
            + json.dumps(data, ensure_ascii=False)
            + "\n\n"
        )

    @stream_with_context
    def generate():
        try:
            s = read(cid)
            previous_workspace = s.get("workspace") or {}
            prior_profile = copy.deepcopy(s["profile"])
            prior_portfolio = copy.deepcopy(s.get("portfolio"))
            prior_right_card = copy.deepcopy(s.get("right_card"))
            s["profile"].pop("_workspace_request", None)
            provisional = resolve_workspace(text, previous_workspace)
            yield event("workspace", {**provisional, "version": s["version"] + 1})
            s["profile"] = extract(text, s["profile"])
            s["version"] += 1
            s.pop("analytics", None)
            s["messages"].append({"role": "user", "text": text.strip()})
            planned_weights = None
            if os.getenv("GEMINI_API_KEY"):
                yield event("status", {"text": "Analyzing investment background and risk budget…"})
                try:
                    s["profile"], planned_weights = gemini_plan(
                        s["messages"], s["profile"]
                    )
                except Exception:
                    app.logger.warning(
                        "Gemini planning unavailable; using local risk budget"
                    )
                    yield event(
                        "notice", {"text": "Model allocation is unavailable; using the local risk budget for this turn."}
                    )
            workspace_hint = s["profile"].pop("_workspace_request", {})
            s["workspace"] = {
                **resolve_workspace(text, previous_workspace, workspace_hint),
                "version": s["version"],
            }
            research_only = (
                bool(s["workspace"]["symbols"])
                and s["workspace"]["kind"]
                in ("security", "comparison", "options", "risk", "macro", "futures")
                and not re.search(
                    "add |remove |enter position|invest |investment amount|capital budget|risk tolerance|risk level|adjust allocation|investment horizon",
                    text,
                )
            )
            if re.fullmatch(
                r"(?:return to |view |open )(?:account|overall|my )?(?:Asset)?(?:allocation|portfolio|workspace)[.!!]?",
                text.strip(),
            ):
                research_only = True
            if research_only:
                s["profile"] = prior_profile
                if prior_portfolio:
                    s["portfolio"] = {
                        **prior_portfolio,
                        "profile": s["profile"],
                        "version": s["version"],
                    }
                else:
                    s["portfolio"] = build(s["profile"], s["version"])
            else:
                if s["workspace"]["kind"] == "allocation" and s["workspace"]["symbols"]:
                    s["profile"]["focus_symbol"] = s["workspace"]["symbols"][0]
                s["portfolio"] = build(s["profile"], s["version"], planned_weights)
            yield event("workspace", s["workspace"])
            s["messages"] = s["messages"][-100:]
            s["portfolio"]["allocation_source"] = (
                prior_portfolio.get("allocation_source", "Local risk budget")
                if research_only and prior_portfolio
                else "Gemini risk budget" if planned_weights else "Local risk budget"
            )
            save(cid, s)
            yield event("portfolio", s["portfolio"])
            answer = ""
            provider = "Local allocation engine"
            if os.getenv("GEMINI_API_KEY"):
                try:
                    from analytics import analyze

                    security_data = []
                    if (
                        s["workspace"]["kind"]
                        in (
                            "security",
                            "comparison",
                            "options",
                            "hedge",
                            "risk",
                            "futures",
                            "allocation",
                            "execution",
                        )
                        and s["workspace"]["symbols"]
                    ):
                        from market import security_research
                        from concurrent.futures import ThreadPoolExecutor

                        yield event(
                            "status", {"text": "Reading prices and financial data for the current security…"}
                        )
                        with ThreadPoolExecutor(max_workers=4) as pool:
                            security_data = list(
                                pool.map(security_research, s["workspace"]["symbols"])
                            )
                        if len(security_data) > 1:
                            from comparison import align_risks

                            security_data = align_risks(security_data)
                        yield event(
                            "security_data",
                            {"workspace": s["workspace"], "securities": security_data},
                        )
                    yield event("status", {"text": "Preparing this turn's research…"})
                    if security_data:
                        context = {
                            "workspace": s["workspace"],
                            "profile": s["profile"],
                            "security_data": [
                                {k: v for k, v in d.items() if k not in ("history",)}
                                for d in security_data
                            ],
                        }
                    else:
                        quantitative = analyze(s["portfolio"])
                        s["analytics"] = quantitative
                        context = {
                            **s["portfolio"],
                            "workspace": s["workspace"],
                            "security_data": [
                                {
                                    k: v
                                    for k, v in d.items()
                                    if k not in ("history", "news")
                                }
                                for d in security_data
                            ],
                            "risk_summary": {
                                k: quantitative[k]
                                for k in (
                                    "months",
                                    "source",
                                    "metrics",
                                    "positions",
                                    "assumptions",
                                )
                            },
                        }
                    if s["workspace"]["kind"] == "macro":
                        context["macro_data"] = fred_data()
                    if security_data and (
                        s["workspace"]["kind"] in ("options", "hedge")
                        or re.search(
                            "options|volatility|straddle|strangle|bullish|bearish|hedge|protection|collar|covered call|put|call|collar",
                            text,
                            re.I,
                        )
                        or any(
                            l.get("instrument") in ("call", "put")
                            for l in (prior_right_card or {})
                            .get("trade", {})
                            .get("legs", [])
                        )
                    ):
                        from market import option_chain

                        yield event(
                            "status", {"text": "Reading actual option contracts and preparing the strategy…"}
                        )
                        context["option_chains"] = {
                            symbol: option_chain(symbol)
                            for symbol in s["workspace"]["symbols"][:3]
                            if not symbol.endswith("=F")
                        }
                        context["option_chain"] = next(
                            iter(context["option_chains"].values()), {}
                        )
                    from trade_plan import parse_plan, build_plan, FUTURES

                    context["futures_multipliers"] = FUTURES
                    context["previous_strategy"] = (prior_right_card or {}).get("trade")
                    from strategy_card import split_output

                    raw_answer, shown, card_shown = "", "", ""
                    for chunk in gemini_stream(s["messages"], context):
                        raw_answer += chunk
                        answer, card = split_output(raw_answer)
                        if answer != shown:
                            if answer.startswith(shown):
                                yield event("delta", {"text": answer[len(shown) :]})
                            else:
                                yield event("replace", {"text": answer})
                            shown = answer
                        if card != card_shown:
                            yield event(
                                "strategy_card",
                                {
                                    "markdown": card,
                                    "version": s["version"],
                                    "symbols": s["workspace"]["symbols"],
                                    "streaming": True,
                                },
                            )
                            card_shown = card
                    answer, card = split_output(raw_answer, final=True)
                    if answer != shown:
                        yield event("replace", {"text": answer})
                    if not card:
                        yield event(
                            "strategy_card", {"markdown": "", "version": s["version"]}
                        )
                    if card:
                        from trade_plan import resolve_plan_data

                        raw_plan = parse_plan(raw_answer)
                        plan_securities, plan_chains = resolve_plan_data(
                            raw_plan, security_data, context.get("option_chains", {})
                        )
                        trade = build_plan(raw_plan, plan_securities, plan_chains)
                        s["right_card"] = dict(
                            markdown=card,
                            trade=trade,
                            version=s["version"],
                            symbols=s["workspace"]["symbols"],
                        )
                        yield event("strategy_card", s["right_card"])
                    if not answer:
                        raise ValueError("empty response")
                    provider = "Gemini"
                except Exception:
                    app.logger.warning(
                        "Gemini request failed; response replaced with local answer"
                    )
                    s.pop("right_card", None)
                    yield event(
                        "strategy_card", {"markdown": "", "version": s["version"]}
                    )
                    answer = workspace_reply(
                        s["workspace"], s["profile"], s["portfolio"]
                    )
                    yield event("replace", {"text": answer})
                    yield event(
                        "notice", {"text": "Gemini  is unavailable; using the local allocation engine for this turn."}
                    )
            else:
                answer = workspace_reply(s["workspace"], s["profile"], s["portfolio"])
                # Local results are emitted as one result; only Gemini is token streamed.
                yield event("delta", {"text": answer})
            if (
                not s.get("right_card")
                or s["right_card"].get("version") != s["version"]
            ):
                from strategy_card import fallback_card

                chain = locals().get("context", {}).get("option_chain")
                if (
                    chain is None
                    and s["workspace"]["symbols"]
                    and re.search("volatility|straddle|strangle", text)
                ):
                    from market import option_chain

                    chain = option_chain(s["workspace"]["symbols"][0])
                s["right_card"] = dict(
                    markdown=fallback_card(s["workspace"], chain),
                    version=s["version"],
                    symbols=s["workspace"]["symbols"],
                )
                yield event("strategy_card", s["right_card"])
            s["messages"].append(
                {"role": "assistant", "text": answer, "provider": provider}
            )
            latest = read(cid)
            if latest.get("analytics", {}).get("version") == s["version"]:
                s["analytics"] = latest["analytics"]
            save(cid, s)
            yield event("done", {"provider": provider, "updated_at": s["updated_at"]})
        finally:
            lock.release()

    return Response(
        generate(), mimetype="text/event-stream", headers={"X-Accel-Buffering": "no"}
    )


@app.post("/api/save")
def persist():
    s = read(identity())
    return jsonify(saved=True, updated_at=s.get("updated_at"))


def investment_signature(workspace, card):
    legs = (card.get("trade") or {}).get("legs") or []
    normalized = [
        {
            "instrument": leg.get("instrument"),
            "symbol": leg.get("symbol"),
            "contract": leg.get("contract"),
            "side": leg.get("side"),
            "quantity": leg.get("quantity"),
        }
        for leg in legs
        if isinstance(leg, dict)
    ]
    return json.dumps(
        {
            "kind": workspace.get("kind"),
            "symbols": workspace.get("symbols", []),
            "legs": normalized,
        },
        sort_keys=True,
        separators=(",", ":"),
    )


@app.post("/api/saved-investments")
def save_investment():
    cid = identity()
    lock = lock_for(cid)
    if not lock.acquire(False):
        return jsonify(error="Wait for the current response to finish"), 409
    try:
        s = read(cid)
        workspace = s.get("workspace") or {}
        card = s.get("right_card") or {}
        legs = (card.get("trade") or {}).get("legs") or []
        if not workspace.get("symbols") or not card.get("markdown") or not legs:
            return jsonify(error="No structured investment recommendation is ready to save"), 400
        title_match = re.search(r"^#{1,3}\s+(.+)$", card["markdown"], re.MULTILINE)
        title = (
            title_match.group(1).strip()
            if title_match
            else workspace.get("title") or "Saved investment"
        )[:100]
        signature = investment_signature(workspace, card)
        saved = s.setdefault("saved_investments", [])
        existing = next((item for item in saved if item.get("signature") == signature), None)
        record = {
            "id": existing.get("id") if existing else secrets.token_urlsafe(10),
            "signature": signature,
            "title": title,
            "kind": workspace.get("kind", "security"),
            "symbols": workspace.get("symbols", [])[:4],
            "workspace": copy.deepcopy(workspace),
            "right_card": copy.deepcopy(card),
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "source_version": s.get("version", 0),
        }
        if existing:
            saved[saved.index(existing)] = record
        else:
            saved.insert(0, record)
        s["saved_investments"] = saved[:40]
        save(cid, s)
        return jsonify(investment=record, saved_investments=s["saved_investments"])
    finally:
        lock.release()


@app.delete("/api/saved-investments/<investment_id>")
def delete_saved_investment(investment_id):
    cid = identity()
    lock = lock_for(cid)
    if not lock.acquire(False):
        return jsonify(error="Wait for the current response to finish"), 409
    try:
        s = read(cid)
        saved = s.get("saved_investments", [])
        filtered = [item for item in saved if item.get("id") != investment_id]
        if len(filtered) == len(saved):
            return jsonify(error="Saved investment not found"), 404
        s["saved_investments"] = filtered
        save(cid, s)
        return jsonify(saved_investments=filtered)
    finally:
        lock.release()


@app.delete("/api/state")
def reset():
    cid = identity()
    lock = lock_for(cid)
    if not lock.acquire(False):
        return jsonify(error="Start a new conversation after generation completes"), 409
    try:
        previous = read(cid)
        save(
            cid,
            dict(
                profile={},
                messages=[],
                portfolio=None,
                version=0,
                saved_investments=previous.get("saved_investments", []),
            ),
        )
    finally:
        lock.release()
    return jsonify(ok=True)


@app.get("/api/export")
def export():
    return Response(
        json.dumps(read(identity()), ensure_ascii=False, indent=2),
        mimetype="application/json",
        headers={"Content-Disposition": "attachment; filename=folio-portfolio.json"},
    )


@app.get("/api/macro")
def macro():
    return jsonify(fred_data())


@app.get("/api/purchases")
def purchases():
    from purchases import purchase_list

    return jsonify(purchase_list(read(identity()).get("portfolio")))


@app.get("/api/market")
def market():
    from market import quotes

    return jsonify(quotes(request.args.get("symbols", "VT,SMH,VGIT,IAU,SGOV")))


@app.get("/api/research")
def research():
    from market import security_research
    from concurrent.futures import ThreadPoolExecutor

    symbols = list(dict.fromkeys(request.args.get("symbols", "").upper().split(",")))
    if not 1 <= len(symbols) <= 4 or any(not SYMBOL.fullmatch(s) for s in symbols):
        return jsonify(error="Enter 1 to 4 valid security symbols"), 400
    with ThreadPoolExecutor(max_workers=4) as pool:
        data = list(pool.map(security_research, symbols))
    if len(data) > 1:
        from comparison import align_risks

        data = align_risks(data)
    return jsonify(securities=data)


@app.get("/api/options")
def options():
    from market import option_chain

    return jsonify(
        option_chain(
            request.args.get("symbol", "SMH").upper(), request.args.get("expiry")
        )
    )


@app.get("/api/analytics")
def analytics():
    from analytics import analyze

    s = read(identity())
    if not s.get("portfolio"):
        return jsonify(error="Create a portfolio first"), 400
    try:
        months = int(request.args.get("months", "3"))
    except ValueError:
        return jsonify(error="Invalid analysis horizon"), 400
    if months not in (1, 3, 6, 12):
        return jsonify(error="Analysis horizon must be 1, 3, 6or 12 months"), 400
    drift = request.args.get("drift", "zero")
    if drift not in ("zero", "historical"):
        return jsonify(error="Invalid drift parameter"), 400
    if request.args.get("calibration", "historical") not in ("historical", "scenario"):
        return jsonify(error="Invalid calibration method"), 400
    result = analyze(
        s["portfolio"],
        months,
        drift,
        request.args.get("calibration", "historical") == "historical",
    )
    cid = identity()
    lock = lock_for(cid)
    if lock.acquire(False):
        try:
            latest = read(cid)
            if latest.get("version") == result["version"]:
                latest["analytics"] = result
                save(cid, latest)
        finally:
            lock.release()
    return jsonify(result)


@app.get("/health")
def health():
    return jsonify(status="ok")


if __name__ == "__main__":
    from waitress import serve

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5050"))
    print(f"Folio V1 running at http://{host}:{port}", flush=True)
    serve(app, host=host, port=port, threads=8, channel_timeout=180)
