from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app import auth
from app.config import Settings, load_settings
from app.pz import apply as apply_mod
from app.pz import ini as ini_mod
from app.pz import mods as mods_mod
from app.pz import process as process_mod
from app.pz import rcon as rcon_mod
from app.pz import sandbox as sandbox_mod
from app.pz import sections as sections_mod
from app.pz import steam as steam_mod

ROOT = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(ROOT / "templates"))


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    app = FastAPI(title="Zomboid Admin", docs_url=None, redoc_url=None)
    app.state.settings = settings
    app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")

    @app.middleware("http")
    async def login_gate(request: Request, call_next):
        request.state.settings = settings
        path = request.url.path
        public = path == "/login" or path.startswith("/static/")
        if not public and not auth.is_logged_in(request):
            return RedirectResponse(url="/login", status_code=303)
        return await call_next(request)

    @app.get("/login", response_class=HTMLResponse)
    async def login_page(request: Request):
        if auth.is_logged_in(request):
            return RedirectResponse("/", status_code=303)
        return TEMPLATES.TemplateResponse(
            request,
            "login.html",
            _base_ctx(request, settings, title="Login"),
        )

    @app.post("/login")
    async def login_submit(request: Request):
        form = await _form_map(request)
        username = form.get("username", "")
        password = form.get("password", "")
        if auth.credentials_match(username, settings.admin_user) and auth.credentials_match(
            password, settings.admin_password
        ):
            auth.login_user(request, username)
            return RedirectResponse("/", status_code=303)
        return TEMPLATES.TemplateResponse(
            request,
            "login.html",
            {**_base_ctx(request, settings, title="Login"), "error": "Invalid username or password."},
            status_code=401,
        )

    @app.post("/logout")
    async def logout(request: Request):
        if not auth.check_csrf(request, (await _form_map(request)).get("csrf")):
            return RedirectResponse("/", status_code=303)
        auth.logout_user(request)
        return RedirectResponse("/login", status_code=303)

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request):
        ctx = _dashboard_ctx(request, settings)
        return TEMPLATES.TemplateResponse(request, "dashboard.html", ctx)

    @app.get("/partials/status", response_class=HTMLResponse)
    async def status_partial(request: Request):
        ctx = _dashboard_ctx(request, settings)
        return TEMPLATES.TemplateResponse(request, "partials/status.html", ctx)

    @app.post("/control/{action}")
    async def control(request: Request, action: str):
        form = await _form_map(request)
        if not auth.check_csrf(request, form.get("csrf")):
            _flash(request, "Invalid CSRF token.", "error")
            return RedirectResponse("/", status_code=303)
        if action == "start":
            result = process_mod.start(settings.pz_start_cmd)
        elif action == "stop":
            result = process_mod.stop(settings.pz_stop_cmd)
        elif action == "restart":
            result = process_mod.restart(settings.pz_start_cmd, settings.pz_stop_cmd)
        else:
            _flash(request, "Unknown action.", "error")
            return RedirectResponse("/", status_code=303)
        _flash(request, result.message, "ok" if result.ok else "error")
        return RedirectResponse("/", status_code=303)

    @app.get("/server", response_class=HTMLResponse)
    async def server_page(request: Request):
        ctx = _server_ctx(request, settings)
        return TEMPLATES.TemplateResponse(request, "server.html", ctx)

    @app.post("/server")
    async def server_save(request: Request):
        form = await _form_map(request)
        if not auth.check_csrf(request, form.get("csrf")):
            _flash(request, "Invalid CSRF token.", "error")
            return RedirectResponse("/server", status_code=303)
        restart = form.get("restart") == "1"
        try:
            ini = _load_ini(settings)
        except FileNotFoundError:
            _flash(request, f"Missing {settings.ini_path}", "error")
            return RedirectResponse("/server", status_code=303)

        for field in ini_mod.CURATED_SERVER_FIELDS:
            key = field["key"]
            if key in {"Mods", "WorkshopItems"}:
                continue
            if field["type"] == "bool":
                ini.set(key, "true" if form.get(key) == "true" else "false")
            elif key in form:
                ini.set(key, form[key])

        for key in list(ini.keys()):
            if ini_mod.is_advanced_key(key) and f"adv.{key}" in form:
                ini.set(key, form[f"adv.{key}"])

        def write() -> None:
            ini_mod.save_ini(settings.ini_path, ini)

        return _apply_and_redirect(request, settings, [write], restart, [settings.ini_path], "/server")

    @app.get("/workshop", response_class=HTMLResponse)
    async def workshop_page(request: Request):
        ctx = _workshop_ctx(request, settings)
        return TEMPLATES.TemplateResponse(request, "workshop.html", ctx)

    @app.post("/workshop")
    async def workshop_save(request: Request):
        form = await _form_map(request)
        if not auth.check_csrf(request, form.get("csrf")):
            _flash(request, "Invalid CSRF token.", "error")
            return RedirectResponse("/workshop", status_code=303)
        restart = form.get("restart") == "1"
        try:
            ini = _load_ini(settings)
        except FileNotFoundError:
            _flash(request, f"Missing {settings.ini_path}", "error")
            return RedirectResponse("/workshop", status_code=303)

        workshop_ids = [v for v in form_list_from_request(request, "workshop_ids") if v]
        mod_ids = [v for v in form_list_from_request(request, "mod_ids") if v]
        add_raw = form.get("add_workshop", "")
        add_id = mods_mod.workshop_id_from_url(add_raw)
        if add_raw and not add_id:
            _flash(request, "Could not parse that Workshop URL or ID.", "error")
            return RedirectResponse("/workshop", status_code=303)
        if add_id and add_id not in workshop_ids:
            workshop_ids.append(add_id)

        ini.set("WorkshopItems", ini_mod.join_list(workshop_ids))
        ini.set("Mods", ini_mod.join_list(mod_ids))

        def write() -> None:
            ini_mod.save_ini(settings.ini_path, ini)

        return _apply_and_redirect(request, settings, [write], restart, [settings.ini_path], "/workshop")

    @app.get("/sandbox", response_class=HTMLResponse)
    async def sandbox_page(request: Request):
        ctx = _sandbox_ctx(request, settings)
        return TEMPLATES.TemplateResponse(request, "sandbox.html", ctx)

    @app.post("/sandbox")
    async def sandbox_save(request: Request):
        form = await _form_map(request)
        if not auth.check_csrf(request, form.get("csrf")):
            _flash(request, "Invalid CSRF token.", "error")
            return RedirectResponse("/sandbox", status_code=303)
        restart = form.get("restart") == "1"
        try:
            existing = sandbox_mod.parse_sandbox_vars(settings.sandbox_path.read_text(encoding="utf-8", errors="replace"))
        except FileNotFoundError:
            _flash(request, f"Missing {settings.sandbox_path}", "error")
            return RedirectResponse("/sandbox", status_code=303)
        except sandbox_mod.LuaParseError as exc:
            _flash(request, f"Could not parse SandboxVars.lua: {exc}", "error")
            return RedirectResponse("/sandbox", status_code=303)

        for key, raw in form.items():
            if not key.startswith("sv."):
                continue
            path = key[3:]
            template = sections_mod.get_nested(existing, path)
            updates_nested = sandbox_mod.unflatten_sandbox(
                {path: sandbox_mod.coerce_lua_value(raw, template)}
            )
            existing = sandbox_mod.merge_sandbox(existing, updates_nested)

        def write() -> None:
            settings.sandbox_path.write_text(
                sandbox_mod.serialize_sandbox_vars(existing), encoding="utf-8"
            )

        return _apply_and_redirect(
            request, settings, [write], restart, [settings.sandbox_path], "/sandbox"
        )

    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        same_site="lax",
        https_only=False,
        max_age=60 * 60 * 24 * 7,
    )
    return app


async def _form_map(request: Request) -> dict[str, str]:
    form = await request.form()
    result: dict[str, str] = {}
    lists: dict[str, list[str]] = {}
    for key in form.keys():
        values = [str(v) for v in form.getlist(key)]
        result[key] = values[-1] if values else ""
        lists[key] = values
    request.state.form_lists = lists
    return result


def _base_ctx(request: Request, settings: Settings, title: str, **extra: Any) -> dict[str, Any]:
    flash = request.session.pop("flash", None)
    stats = process_mod.get_stats(settings.pz_status_cmd)
    ctx = {
        "title": title,
        "user": auth.current_user(request),
        "csrf": auth.csrf_token(request),
        "flash": flash,
        "stats": stats,
        "running": stats.running,
        "uptime": process_mod.format_uptime(stats.uptime_seconds),
        "server_name": settings.pz_server_name,
        "nav": title.lower(),
    }
    ctx.update(extra)
    return ctx


def _flash(request: Request, message: str, kind: str = "ok") -> None:
    request.session["flash"] = {"message": message, "kind": kind}


def _load_ini(settings: Settings) -> ini_mod.IniFile:
    if not settings.ini_path.exists():
        raise FileNotFoundError(settings.ini_path)
    return ini_mod.load_ini(settings.ini_path)


def _apply_and_redirect(
    request: Request,
    settings: Settings,
    write_fns,
    restart: bool,
    files: list[Path],
    dest: str,
):
    try:
        result = apply_mod.apply_writes(settings, write_fns, restart, files)
    except apply_mod.UnsafeEditError as exc:
        _flash(request, str(exc), "error")
        return RedirectResponse(dest, status_code=303)
    kind = "ok" if result.ok else "error"
    extra = f" Backup: {result.backup_dir}" if result.backup_dir else ""
    _flash(request, result.message + extra, kind)
    return RedirectResponse(dest, status_code=303)


def _dashboard_ctx(request: Request, settings: Settings) -> dict[str, Any]:
    stats = process_mod.get_stats(settings.pz_status_cmd)
    public_name = settings.pz_server_name
    max_players = ""
    player_count = None
    players: list[str] = []
    rcon_ok = False
    try:
        ini = _load_ini(settings)
        public_name = ini.get("PublicName", public_name)
        max_players = ini.get("MaxPlayers", "")
        rcon_password = ini.get("RCONPassword", "")
        rcon_port = settings.rcon_port or int(ini.get("RCONPort") or 0)
        if rcon_password and rcon_port:
            listing = rcon_mod.fetch_players(settings.rcon_host, rcon_port, rcon_password)
            if listing is not None:
                rcon_ok = True
                players = listing.names
                player_count = listing.count
    except FileNotFoundError:
        ini = None

    log_tail = process_mod.tail_logs(settings.logs_dir)
    return _base_ctx(
        request,
        settings,
        title="Dashboard",
        nav="dashboard",
        public_name=public_name,
        max_players=max_players,
        player_count=player_count,
        players=players,
        rcon_ok=rcon_ok,
        log_tail=log_tail,
        stats=stats,
        running=stats.running,
        uptime=process_mod.format_uptime(stats.uptime_seconds),
    )


def _server_ctx(request: Request, settings: Settings) -> dict[str, Any]:
    missing = not settings.ini_path.exists()
    curated = []
    advanced = []
    if not missing:
        ini = _load_ini(settings)
        values = ini.as_dict()
        for field in ini_mod.CURATED_SERVER_FIELDS:
            if field["type"] == "hidden":
                continue
            curated.append({**field, "value": values.get(field["key"], "")})
        for key, value in ini.items():
            if ini_mod.is_advanced_key(key):
                advanced.append({"key": key, "value": value})
    return _base_ctx(
        request,
        settings,
        title="Server",
        nav="server",
        missing=missing,
        ini_path=str(settings.ini_path),
        curated=curated,
        advanced=advanced,
    )


def _workshop_ctx(request: Request, settings: Settings) -> dict[str, Any]:
    missing = not settings.ini_path.exists()
    workshop_ids: list[str] = []
    mod_ids: list[str] = []
    items = []
    orphan_mods: list[str] = []
    titles: dict[str, str] = {}
    downloaded_mods: list[mods_mod.ModInfo] = []
    if not missing:
        ini = _load_ini(settings)
        workshop_ids = ini_mod.split_list(ini.get("WorkshopItems", ""))
        mod_ids = ini_mod.split_list(ini.get("Mods", ""))
        titles = steam_mod.fetch_workshop_titles(workshop_ids)
        roots = mods_mod.find_mod_roots(settings.workshop_search_dirs)
        seen: set[str] = set()
        for root in roots:
            workshop_id = ""
            for part in root.parts:
                if part.isdigit() and len(part) >= 6:
                    workshop_id = part
            info = mods_mod.load_mod_info_from_dir(root, workshop_id=workshop_id)
            if info and info.mod_id and info.mod_id not in seen:
                seen.add(info.mod_id)
                downloaded_mods.append(info)

        mods_by_workshop: dict[str, list[mods_mod.ModInfo]] = {}
        for info in downloaded_mods:
            mods_by_workshop.setdefault(info.workshop_id or "", []).append(info)

        claimed_mod_ids: set[str] = set()
        for wid in workshop_ids:
            pack_mods = mods_by_workshop.get(wid, [])
            pack_mod_ids = [m.mod_id for m in pack_mods]
            claimed_mod_ids.update(pack_mod_ids)
            enabled_here = [m for m in pack_mods if m.mod_id in mod_ids]
            warning = ""
            if not pack_mods:
                warning = "Not downloaded yet — restart the server so Steam can fetch this item."
            elif pack_mod_ids and not enabled_here:
                warning = "Downloaded, but no Mod ID from this package is enabled."
            items.append(
                {
                    "workshop_id": wid,
                    "title": titles.get(wid, ""),
                    "downloaded": bool(pack_mods),
                    "mods": pack_mods,
                    "warning": warning,
                }
            )

        for mid in mod_ids:
            known = next((m for m in downloaded_mods if m.mod_id == mid), None)
            if known and known.workshop_id and known.workshop_id in workshop_ids:
                continue
            if not known:
                orphan_mods.append(mid)

    enabled_set = set(mod_ids)
    return _base_ctx(
        request,
        settings,
        title="Workshop",
        nav="workshop",
        missing=missing,
        ini_path=str(settings.ini_path),
        items=items,
        workshop_ids=workshop_ids,
        mod_ids=mod_ids,
        enabled_set=enabled_set,
        downloaded_mods=downloaded_mods,
        orphan_mods=orphan_mods,
    )


def _sandbox_ctx(request: Request, settings: Settings) -> dict[str, Any]:
    missing = not settings.sandbox_path.exists()
    parse_error = ""
    sandbox_sections: list[sections_mod.Section] = []
    if not missing:
        try:
            data = sandbox_mod.parse_sandbox_vars(
                settings.sandbox_path.read_text(encoding="utf-8", errors="replace")
            )
            workshop_ids: list[str] = []
            mod_ids: list[str] = []
            if settings.ini_path.exists():
                ini = _load_ini(settings)
                workshop_ids = ini_mod.split_list(ini.get("WorkshopItems", ""))
                mod_ids = ini_mod.split_list(ini.get("Mods", ""))
            mod_packs = mods_mod.collect_enabled_mod_options(
                settings.workshop_search_dirs, workshop_ids, mod_ids
            )
            mod_sections = []
            all_options: list[mods_mod.SandboxOption] = []
            for info, options in mod_packs:
                mod_sections.append((info.mod_id, info.name or info.mod_id, options))
                all_options.extend(options)
            sections_mod.seed_mod_defaults(data, all_options)
            sandbox_sections = sections_mod.build_sandbox_sections(data, mod_sections)
        except sandbox_mod.LuaParseError as exc:
            parse_error = str(exc)
    return _base_ctx(
        request,
        settings,
        title="Sandbox",
        nav="sandbox",
        missing=missing,
        parse_error=parse_error,
        sandbox_path=str(settings.sandbox_path),
        sections=sandbox_sections,
    )


def form_list_from_request(request: Request, key: str) -> list[str]:
    lists = getattr(request.state, "form_lists", {})
    values = lists.get(key)
    if values is None:
        return []
    return [v for v in values if v != ""]


app = create_app()
