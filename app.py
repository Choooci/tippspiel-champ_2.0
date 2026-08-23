# app.py
# Bundesliga Tippspiel 2.0 - mit Supabase Datenbank

import streamlit as st
import pandas as pd
from supabase import create_client, Client
import random

# --- Verbindung zu Supabase herstellen ---
# Die Zugangsdaten kommen aus den Streamlit Secrets, nie aus dem Code selbst
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

# --- Seiteneinstellungen ---
st.set_page_config(page_title="Bundesliga Tippspiel 2.0", layout="wide")

# --- Passwortschutz ---
PASSWORT = "040822"
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔒 Bundesliga Tippspiel 2.0")
    pw_input = st.text_input("Passwort eingeben", type="password")
    if st.button("Einloggen"):
        if pw_input == PASSWORT:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Falsches Passwort")
    st.stop()

# --- Aktuelle Saison festlegen ---
# Diese Zahl bei neuer Saison einfach anpassen
AKTUELLE_SAISON = "2026-27"

# --- Die feste Draft-Reihenfolge (Snake-Draft-Muster) ---
# 1234432112344321 - zweimal hintereinander für 2 Runden falls benötigt
DRAFT_REIHENFOLGE = "1234432112344321" * 2  # 32 Zeichen für bis zu 32 Picks

# --- Hilfsfunktionen für Datenbankzugriffe ---

def get_or_create_season(season_name):
    """Sucht die Saison in der Datenbank oder legt sie neu an."""
    result = supabase.table("seasons").select("*").eq("season_name", season_name).execute()
    if len(result.data) > 0:
        return result.data[0]
    else:
        new_season = supabase.table("seasons").insert({
            "season_name": season_name,
            "draft_completed": False
        }).execute()
        return new_season.data[0]

def get_players():
    """Holt alle Spieler aus der Datenbank."""
    result = supabase.table("players").select("*").order("id").execute()
    return result.data

def get_teams_for_season(season_id):
    """Holt alle Teams für die aktuelle Saison."""
    result = supabase.table("teams").select("*").eq("season_id", season_id).execute()
    return result.data

def get_draft_positions(season_id):
    """Holt die ausgeloste Reihenfolge (wer ist 1., 2., 3., 4.)."""
    result = supabase.table("draft_positions").select("*, players(name)").eq("season_id", season_id).order("position").execute()
    return result.data

def get_draft_picks(season_id):
    """Holt alle bisherigen Picks der Saison."""
    result = supabase.table("draft_picks").select("*, players(name), teams(team_name, logo_url)").eq("season_id", season_id).order("pick_number").execute()
    return result.data

def save_draft_positions(season_id, player_ids):
    """Speichert die zufällig ausgeloste Reihenfolge."""
    positions = list(range(1, len(player_ids) + 1))
    random.shuffle(positions)
    for player_id, position in zip(player_ids, positions):
        supabase.table("draft_positions").insert({
            "season_id": season_id,
            "player_id": player_id,
            "position": position
        }).execute()

def save_pick(season_id, player_id, team_id, pick_number):
    """Speichert einen einzelnen Draft-Pick."""
    supabase.table("draft_picks").insert({
        "season_id": season_id,
        "player_id": player_id,
        "team_id": team_id,
        "pick_number": pick_number
    }).execute()

def mark_draft_completed(season_id):
    """Markiert den Draft als abgeschlossen, damit er gesperrt wird."""
    supabase.table("seasons").update({"draft_completed": True}).eq("id", season_id).execute()

# --- Hauptbereich der App ---

st.title("⚽ Bundesliga Tippspiel 2.0")

# Saison in Datenbank sicherstellen
season = get_or_create_season(AKTUELLE_SAISON)
season_id = season["id"]

st.subheader(f"Saison {AKTUELLE_SAISON}")

# --- Bereich: Draft (nur falls noch nicht abgeschlossen) ---

if not season["draft_completed"]:
    st.header("🎲 Team-Draft")

    players = get_players()
    teams = get_teams_for_season(season_id)

    if len(teams) == 0:
        st.warning("Für diese Saison sind noch keine Teams hinterlegt. Bitte zuerst über den Admin-Bereich eintragen.")
        st.stop()

    positions = get_draft_positions(season_id)

    # --- Schritt A: Auslosung der Reihenfolge (falls noch nicht geschehen) ---
    if len(positions) == 0:
        st.write("Die Reihenfolge wurde noch nicht ausgelost.")
        if st.button("🎲 Jetzt Reihenfolge auslosen!"):
            player_ids = [p["id"] for p in players]
            save_draft_positions(season_id, player_ids)
            st.rerun()
    else:
        # Reihenfolge anzeigen
        st.write("**Ausgeloste Reihenfolge:**")
        cols = st.columns(len(positions))
        for idx, pos_entry in enumerate(positions):
            with cols[idx]:
                st.metric(f"Position {pos_entry['position']}", pos_entry["players"]["name"])

        # --- Schritt B: Der eigentliche Draft ---
        picks = get_draft_picks(season_id)
        picked_team_ids = [p["team_id"] for p in picks]
        available_teams = [t for t in teams if t["id"] not in picked_team_ids]

        current_pick_number = len(picks) + 1
        total_teams = len(teams)

        if current_pick_number > total_teams:
            st.success("Alle Teams wurden gepickt!")
            if st.button("✅ Draft abschließen und Saison starten"):
                mark_draft_completed(season_id)
                st.rerun()
        else:
            # Wer ist gerade dran? Anhand der festen Reihenfolge herausfinden
            aktuelle_position = int(DRAFT_REIHENFOLGE[current_pick_number - 1])
            aktueller_spieler = next(p for p in positions if p["position"] == aktuelle_position)
            spieler_name = aktueller_spieler["players"]["name"]
            spieler_id = aktueller_spieler["player_id"]

            st.write(f"**Pick {current_pick_number} von {total_teams}**")
            st.write(f"🎯 **{spieler_name} ist dran!**")

            # Auswahl der Teams mit Logo-Anzeige
            team_options = {t["team_name"]: t["id"] for t in available_teams}

            cols = st.columns(4)
            for idx, team in enumerate(available_teams):
                with cols[idx % 4]:
                    if team.get("logo_url"):
                        st.image(team["logo_url"], width=80)
                    if st.button(team["team_name"], key=f"pick_{team['id']}"):
                        save_pick(season_id, spieler_id, team["id"], current_pick_number)
                        st.rerun()

        # Bisherige Picks anzeigen
        if len(picks) > 0:
            st.write("---")
            st.write("**Bisherige Picks:**")
            picks_df = pd.DataFrame([{
                "Pick": p["pick_number"],
                "Spieler": p["players"]["name"],
                "Team": p["teams"]["team_name"]
            } for p in picks])
            st.dataframe(picks_df, hide_index=True)

else:
    st.success("✅ Draft für diese Saison abgeschlossen!")
    st.header("🏆 Saison läuft")
    # Hier kommt später Dein bestehender Tippspiel-Code hin
    # (Tipps abgeben, Tabelle, Auswertung etc.)
    st.info("Hier kommt der Rest der App hin (Tipps, Tabelle etc.) – sag Bescheid, dann bauen wir das ein!")
