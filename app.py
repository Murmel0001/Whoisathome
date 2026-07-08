import json
import os
import threading
from threading import Lock

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse


# -------------------------------------------------
# Konfiguration über Umgebungsvariablen
# -------------------------------------------------

PERSONS_ENV = os.getenv("PERSONS", "person1,person2,person3,person4,person5")
ALLOWED_PERSONS = {
    person.strip()
    for person in PERSONS_ENV.split(",")
    if person.strip()
}

STATE_FILE = os.getenv("STATE_FILE", "/data/home_state.json")

lock = Lock()


# -------------------------------------------------
# Zustand laden/speichern
# -------------------------------------------------

def load_state():
    if not os.path.exists(STATE_FILE):
        return {person: False for person in ALLOWED_PERSONS}

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
    except Exception:
        data = {}

    state = {}

    for person in ALLOWED_PERSONS:
        state[person] = bool(data.get(person, False))

    return state


def save_state():
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)

    with open(STATE_FILE, "w", encoding="utf-8") as file:
        json.dump(home_state, file, indent=2)


home_state = load_state()


# -------------------------------------------------
# API 1: Setzen
# Port 8000
# -------------------------------------------------

set_app = FastAPI(
    docs_url=None,
    redoc_url=None,
    openapi_url=None
)


@set_app.get("/whoisathome/{person}/{value}", response_class=PlainTextResponse)
def set_person_status_clean(person: str, value: str, request: Request):
    """
    Beispiel:
    /whoisathome/person1/true
    /whoisathome/person1/false
    """

    # Keine Query-Parameter erlauben.
    # Also z. B. ?x=123 wird abgelehnt.
    if request.query_params:
        raise HTTPException(status_code=400, detail="Query parameters are not allowed")

    if person not in ALLOWED_PERSONS:
        raise HTTPException(status_code=404, detail="Unknown person")

    value = value.lower()

    if value not in ["true", "false"]:
        raise HTTPException(status_code=400, detail="Value must be true or false")

    with lock:
        home_state[person] = value == "true"
        save_state()

    return "ok"


@set_app.get("/whoisathome/{assignment}", response_class=PlainTextResponse)
def set_person_status_assignment(assignment: str, request: Request):
    """
    Alternative Schreibweise:
    /whoisathome/person1=true
    /whoisathome/person1=false
    """

    # Keine Query-Parameter erlauben.
    if request.query_params:
        raise HTTPException(status_code=400, detail="Query parameters are not allowed")

    if "=" not in assignment:
        raise HTTPException(status_code=400, detail="Invalid format")

    person, value = assignment.split("=", 1)

    if person not in ALLOWED_PERSONS:
        raise HTTPException(status_code=404, detail="Unknown person")

    value = value.lower()

    if value not in ["true", "false"]:
        raise HTTPException(status_code=400, detail="Value must be true or false")

    with lock:
        home_state[person] = value == "true"
        save_state()

    return "ok"


# -------------------------------------------------
# API 2: Abfragen
# Port 8001
# -------------------------------------------------

status_app = FastAPI(
    docs_url=None,
    redoc_url=None,
    openapi_url=None
)


@status_app.get("/status/{person}", response_class=PlainTextResponse)
def get_person_status(person: str, request: Request):
    """
    Beispiel:
    /status/person1

    Antwort:
    true
    oder
    false
    """

    if request.query_params:
        raise HTTPException(status_code=400, detail="Query parameters are not allowed")

    if person not in ALLOWED_PERSONS:
        raise HTTPException(status_code=404, detail="Unknown person")

    with lock:
        value = home_state[person]

    return "true" if value else "false"


@status_app.get("/status", response_class=PlainTextResponse)
def get_all_status(request: Request):
    """
    Optional:
    /status

    Antwort z. B.:
    person1=true
    person2=false
    """

    if request.query_params:
        raise HTTPException(status_code=400, detail="Query parameters are not allowed")

    with lock:
        lines = [
            f"{person}={'true' if home_state[person] else 'false'}"
            for person in sorted(ALLOWED_PERSONS)
        ]

    return "\n".join(lines)


# -------------------------------------------------
# Beide APIs starten
# -------------------------------------------------

def run_set_api():
    uvicorn.run(
        set_app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )


def run_status_api():
    uvicorn.run(
        status_app,
        host="0.0.0.0",
        port=8001,
        log_level="info"
    )


if __name__ == "__main__":
    set_thread = threading.Thread(target=run_set_api)
    status_thread = threading.Thread(target=run_status_api)

    set_thread.start()
    status_thread.start()

    set_thread.join()
    status_thread.join()