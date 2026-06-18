import io
import os
import re
import tempfile
import zipfile
from pathlib import Path

from fastapi import Cookie, Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.requests import Request

from app import auth, db
from app.email_utils import send_email
from app.fit_parser import parse_fit_file
from app.zones import MAX_HR, ZONE_COLORS

BASE_DIR = Path(__file__).resolve().parent
IS_PRODUCTION = bool(os.environ.get("RENDER") or os.environ.get("RAILWAY_ENVIRONMENT"))
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

app = FastAPI(title="Running Dashboard")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

db.init_db()


class Credentials(BaseModel):
    email: str
    password: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    password: str


def get_current_user(session: str | None = Cookie(default=None)) -> dict:
    user_id = auth.verify_session_token(session) if session else None
    user = db.get_user_by_id(user_id) if user_id else None
    if not user:
        raise HTTPException(401, "Not authenticated")
    return user


def get_current_user_optional(session: str | None = Cookie(default=None)) -> dict | None:
    user_id = auth.verify_session_token(session) if session else None
    return db.get_user_by_id(user_id) if user_id else None


def _set_session_cookie(response, user_id: int):
    response.set_cookie(
        auth.SESSION_COOKIE_NAME,
        auth.create_session_token(user_id),
        max_age=auth.SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=IS_PRODUCTION,
    )


@app.get("/", response_class=HTMLResponse)
def index(request: Request, user: dict | None = Depends(get_current_user_optional)):
    if not user:
        return RedirectResponse("/login")
    return templates.TemplateResponse("index.html", {
        "request": request, "max_hr": MAX_HR, "zone_colors": ZONE_COLORS,
        "user_email": user["email"], "is_admin": user["is_admin"],
    })


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, user: dict | None = Depends(get_current_user_optional)):
    if user:
        return RedirectResponse("/")
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/signup", response_class=HTMLResponse)
def signup_page(request: Request, user: dict | None = Depends(get_current_user_optional)):
    if user:
        return RedirectResponse("/")
    return templates.TemplateResponse("signup.html", {"request": request})


@app.post("/api/signup")
def signup(creds: Credentials):
    email = creds.email.strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(400, "Enter a valid email address")
    if len(creds.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    if db.get_user_by_email(email):
        raise HTTPException(400, "An account with that email already exists")

    is_first_user = not db.any_users_exist()
    user = db.create_user(email, auth.hash_password(creds.password), is_admin=is_first_user)

    response = RedirectResponse("/", status_code=303)
    _set_session_cookie(response, user["id"])
    return response


@app.post("/api/login")
def login(creds: Credentials):
    email = creds.email.strip().lower()
    user = db.get_user_by_email(email)
    if not user or not auth.verify_password(creds.password, user["password_hash"]):
        raise HTTPException(401, "Incorrect email or password")

    response = RedirectResponse("/", status_code=303)
    _set_session_cookie(response, user["id"])
    return response


@app.post("/api/logout")
def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(auth.SESSION_COOKIE_NAME)
    return response


@app.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_page(request: Request):
    return templates.TemplateResponse("forgot_password.html", {"request": request})


@app.get("/reset-password", response_class=HTMLResponse)
def reset_password_page(request: Request, token: str = ""):
    return templates.TemplateResponse("reset_password.html", {"request": request, "token": token})


@app.post("/api/forgot-password")
def forgot_password(req: ForgotPasswordRequest, request: Request):
    email = req.email.strip().lower()
    user = db.get_user_by_email(email)
    if user:
        token = auth.create_reset_token(user["id"], user["password_hash"])
        reset_url = f"{str(request.base_url).rstrip('/')}/reset-password?token={token}"
        send_email(
            user["email"],
            "Reset your RunDash password",
            f"Click the link below to reset your password. This link expires in 1 hour.\n\n{reset_url}\n\n"
            "If you didn't request this, you can ignore this email.",
        )
    # Always return success, whether or not the email exists, so we don't leak which emails are registered.
    return {"message": "If an account with that email exists, a reset link has been sent."}


@app.post("/api/reset-password")
def reset_password(req: ResetPasswordRequest):
    data = auth.decode_reset_token(req.token)
    if not data:
        raise HTTPException(400, "This reset link is invalid or has expired")

    user = db.get_user_by_id(data["user_id"])
    if not user or user["password_hash"] != data["password_hash"]:
        raise HTTPException(400, "This reset link has already been used or is no longer valid")
    if len(req.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")

    db.update_password(user["id"], auth.hash_password(req.password))
    return {"message": "Password updated. You can now log in."}


@app.get("/api/me")
def me(user: dict = Depends(get_current_user)):
    return {"email": user["email"], "is_admin": user["is_admin"]}


def _parse_and_store(fit_bytes: bytes, filename: str, user_id: int) -> dict:
    with tempfile.NamedTemporaryFile(suffix=".fit", delete=False) as tmp:
        tmp.write(fit_bytes)
        tmp_path = tmp.name
    try:
        run_summary, records = parse_fit_file(tmp_path, filename)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    if not records:
        raise ValueError("No record data found in FIT file")

    run_id = db.insert_run(run_summary, records, user_id)
    return {"id": run_id, **run_summary}


@app.post("/api/upload")
async def upload_fit(files: list[UploadFile] = File(...), user: dict = Depends(get_current_user)):
    results = []
    errors = []

    for file in files:
        name_lower = file.filename.lower()
        content = await file.read()

        if name_lower.endswith(".zip"):
            try:
                with zipfile.ZipFile(io.BytesIO(content)) as zf:
                    fit_names = [n for n in zf.namelist() if n.lower().endswith(".fit")]
                    if not fit_names:
                        errors.append({"filename": file.filename, "error": "Zip contains no .fit file"})
                        continue
                    for fit_name in fit_names:
                        try:
                            results.append(_parse_and_store(zf.read(fit_name), fit_name, user["id"]))
                        except Exception as e:
                            errors.append({"filename": fit_name, "error": str(e)})
            except zipfile.BadZipFile:
                errors.append({"filename": file.filename, "error": "Invalid zip file"})
        elif name_lower.endswith(".fit"):
            try:
                results.append(_parse_and_store(content, file.filename, user["id"]))
            except Exception as e:
                errors.append({"filename": file.filename, "error": str(e)})
        else:
            errors.append({"filename": file.filename, "error": "Only .fit or .zip files are supported"})

    if not results and errors:
        raise HTTPException(400, errors[0]["error"])

    return {"uploaded": results, "errors": errors}


@app.get("/api/runs")
def get_runs(user: dict = Depends(get_current_user)):
    return db.list_runs(user["id"], is_admin=user["is_admin"])


@app.get("/api/runs/{run_id}")
def get_run_detail(run_id: int, user: dict = Depends(get_current_user)):
    run = db.get_run(run_id, user["id"], is_admin=user["is_admin"])
    if not run:
        raise HTTPException(404, "Run not found")
    run["records"] = db.get_run_records(run_id)
    return run


@app.delete("/api/runs/{run_id}")
def remove_run(run_id: int, user: dict = Depends(get_current_user)):
    if not db.delete_run(run_id, user["id"], is_admin=user["is_admin"]):
        raise HTTPException(404, "Run not found")
    return {"deleted": run_id}


@app.get("/api/trends")
def get_trends(user: dict = Depends(get_current_user)):
    runs = db.list_runs(user["id"], is_admin=user["is_admin"])
    runs_sorted = sorted(runs, key=lambda r: r["start_time"] or "")
    return {
        "labels": [r["start_time"] for r in runs_sorted],
        "avg_hr": [r["avg_hr"] for r in runs_sorted],
        "zone2_pct": [r["zone2_pct"] for r in runs_sorted],
        "distance_km": [r["distance_km"] for r in runs_sorted],
    }
