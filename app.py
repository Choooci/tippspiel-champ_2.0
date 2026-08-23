# bundesliga_tippspiel.py

import streamlit as st
import pandas as pd
import requests
import random
import json
from pathlib import Path
from PIL import Image
import base64
from io import BytesIO
from datetime import datetime
from supabase import create_client, Client

# ============================================================
# KONFIGURATION
# ============================================================

PASSWORT = "040822"
AKTUELLE_SAISON_NAME = "2026-27"
AKTUELLE_SAISON_KEY = 5  # neuer Schlüssel für die neue Saison im Tippspiel
DRAFT_SNAKE_ORDER = "1234432112344321"  # Reihenfolge für 16 Picks (4 Runden)

# --- Supabase Verbindung ---
SUPABASE_URL = st.secrets["supabase_url"]
SUPABASE_KEY = st.secrets["supabase_key"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ============================================================
# ALTE SAISON-DATEN (bleiben hartcodiert wie bisher)
# ============================================================

season_dict = {
    1: '2022-23',
    2: '2023-24',
    3: '2024-25',
    4: '2025-26',
    AKTUELLE_SAISON_KEY: AKTUELLE_SAISON_NAME,  # neue Saison wird hier ergänzt
}

season_api_urls = {
    1: "https://www.openligadb.de/api/getbltable/bl1/2022",
    2: "https://www.openligadb.de/api/getbltable/bl1/2023",
    3: "https://www.openligadb.de/api/getbltable/bl1/2024",
    4: "https://www.openligadb.de/api/getbltable/bl1/2025",
    AKTUELLE_SAISON_KEY: "https://www.openligadb.de/api/getbltable/bl1/2026",
}

# --- Tipp-Listen (nur alte Saisons, hartcodiert) ---
paul1 = ["Schalke", "Bremen", "Hoffenheim", "Mainz"]
tuschi1 = ["Hertha", "Augsburg", "Union", "Gladbach"]
choci1 = ["Bochum", "Stuttgart", "Köln", "Freiburg"]
paul2 = ["Bochum", "Hoffenheim", "Köln", "Frankfurt"]
tuschi2 = ["Darmstadt", "Bremen", "Stuttgart", "Gladbach"]
choci2 = ["Heidenheim", "Augsburg", "Mainz", "Wolfsburg"]
dan3 = ["Heidenheim", "Bremen", "Augsburg", "Dortmund"]
paul3 = ["Kiel", "Mainz", "Wolfsburg", "Frankfurt"]
tuschi3 = ["Union", "Pauli", "Freiburg", "Stuttgart"]
choci3 = ["Bochum", "Hoffenheim", "Gladbach", "Leipzig"]
dan4 = ["Köln", "Bremen", "Augsburg", "Dortmund"]
paul4 = ["Hamburg", "Union", "Leipzig", "Leverkusen"]
tuschi4 = ["Heidenheim", "Gladbach", "Pauli", "Freiburg"]
choci4 = ["Hoffenheim", "Mainz", "Wolfsburg", "Stuttgart"]

tipps_dict = {
    1: {"Paul": paul1, "Tuschi": tuschi1, "Choci": choci1},
    2: {"Paul": paul2, "Tuschi": tuschi2, "Choci": choci2},
    3: {"Dan": dan3, "Paul": paul3, "Tuschi": tuschi3, "Choci": choci3},
    4: {"Dan": dan4, "Paul": paul4, "Tuschi": tuschi4, "Choci": choci4},
}

# --- Top-6 Tipps (nur alte Saisons) ---
top6_tipps = {
    1: {
        "Paul": ["Bayern", "Dortmund", "Leipzig", "Leverkusen", "Gladbach", "Wolfsburg"],
        "Tuschi": ["Bayern", "Leipzig", "Dortmund", "Frankfurt", "Leverkusen", "Hoffenheim"],
        "Choci": ["-", "Leverkusen", "Dortmund", "RB Scheiße", "Wolfsburg", "Frankfurt"],
    },
    2: {
        "Paul": ["Leverkusen", "Bayern", "Dosenkacke", "DasTeammitMatsHummels", "Union", "Gladbach"],
        "Tuschi": ["Harry Kane", "Vizekusen", "Dortmund", "Leipzig", "Union", "Frankfurt"],
        "Choci": ["Kevin Volland", "FC Bauern", "Vizekusen", "Doofmund", "Dosenverein", "Frankfurt"],
    },
    3: {
        "Dan": ["nicht getippt wir dullis", "-", "-", "-", "-", "-"],
        "Paul": ["nicht getippt wir dullis", "-", "-", "-", "-", "-"],
        "Tuschi": ["nicht getippt wir dullis", "-", "-", "-", "-", "-"],
        "Choci": ["nicht getippt wir dullis", "-", "-", "-", "-", "-"],
    },
    4: {
        "Dan": ["Bayern", "Frankfurt", "Dortmund", "Stuttgart", "Lverkusen", "Leipzig"],
        "Paul": ["Bayern", "Frankfurt", "Stuhlgang", "Dortmund", "Freiburg", "Leverkusen"],
        "Tuschi": ["Bayern", "Dortmund", "Frankfurt", "Scheißig", "Stuttgart", "Leverkusen", "Augsburg"],
        "Choci": ["Im Herzen von Europa liegt die Eintracht am Main", "FC Bauern", "Freiburg", "Leverbusen", "Dortmund", "Stuttgart"],
    }
}

# --- Teams Informationen (Kurzname -> voller Name + Logo lokal für alte Saisons) ---
teams_info = {
    "Köln": {"name": "1. FC Köln", "logo": "Logos/Koeln.png"},
    "Bremen": {"name": "Werder Bremen", "logo": "Logos/Bremen.png"},
    "Augsburg": {"name": "FC Augsburg", "logo": "Logos/Augsburg.png"},
    "Dortmund": {"name": "Borussia Dortmund", "logo": "Logos/Dortmund.png"},
    "Hamburg": {"name": "Hamburger SV", "logo": "Logos/Hamburg.png"},
    "Union": {"name": "1. FC Union Berlin", "logo": "Logos/Union.png"},
    "Leipzig": {"name": "RB Leipzig", "logo": "Logos/Leipzig.png"},
    "Leverkusen": {"name": "Bayer 04 Leverkusen", "logo": "Logos/Leverkusen.png"},
    "Heidenheim": {"name": "1. FC Heidenheim 1846", "logo": "Logos/Heidenheim.png"},
    "Gladbach": {"name": "Borussia Mönchengladbach", "logo": "Logos/Gladbach.png"},
    "Pauli": {"name": "FC St. Pauli", "logo": "Logos/Pauli.png"},
    "Freiburg": {"name": "SC Freiburg", "logo": "Logos/Freiburg.png"},
    "Hoffenheim": {"name": "TSG Hoffenheim", "logo": "Logos/Hoffenheim.png"},
    "Mainz": {"name": "1. FSV Mainz 05", "logo": "Logos/Mainz.png"},
    "Wolfsburg": {"name": "VfL Wolfsburg", "logo": "Logos/Wolfsburg.png"},
    "Stuttgart": {"name": "VfB Stuttgart", "logo": "Logos/Stuttgart.png"},
    "Frankfurt": {"name": "Eintracht Frankfurt", "logo": "Logos/Frankfurt.png"},
    "Darmstadt": {"name": "SV Darmstadt 98", "logo": "Logos/Darmstadt.png"},
    "Bochum": {"name": "VfL Bochum", "logo": "Logos/Bochum.png"},
    "Kiel": {"name": "Holstein Kiel", "logo": "Logos/Kiel.png"},
    "Hertha": {"name": "Hertha BSC", "logo": "Logos/Hertha.png"},
    "Schalke": {"name": "FC Schalke 04", "logo": "Logos/Schalke.png"},
    "Bayern": {"name": "FC Bauern München", "logo": "Logos/Bayern.png"},
}

# ============================================================
# SUPABASE-FUNKTIONEN (für die neue Saison mit Draft)
# ============================================================

def get_or_create_season(season_name):
    """Holt die Saison aus Supabase oder legt sie neu an."""
    try:
        result = supabase.table("seasons").select("*").eq("season_name", season_name).single().execute()
        if result.data:
            return result.data
    except Exception:
        pass

    # Saison existiert noch nicht -> neu anlegen
    new_season = {
        "season_name": season_name,
        "draft_completed": False,
        "draft_order": None,
        "draft_stage": "waiting"  # waiting, drawing, team_draft, completed
    }
    result = supabase.table("seasons").insert(new_season).execute()
    return result.data[0]


def get_players():
    """Holt alle Spieler aus Supabase."""
    try:
        result = supabase.table("players").select("*").execute()
        return result.data if result.data else []
    except Exception:
        return []


def get_teams_for_season(season_id):
    """Holt alle Teams, die für die Saison in Supabase hinterlegt sind."""
    try:
        result = supabase.table("teams").select("*").eq("season_id", season_id).execute()
        return result.data if result.data else []
    except Exception:
        return []


def load_teams_from_openligadb(season_year, season_id):
    """Lädt die 18 Bundesliga-Teams von OpenLigaDB und speichert sie in Supabase."""
    try:
        url = f"https://api.openligadb.de/getbltable/bl1/{season_year}"
        response = requests.get(url)
        response.raise_for_status()
        table_data = response.json()

        # Alte Teams dieser Saison löschen, damit keine Duplikate entstehen
        supabase.table("teams").delete().eq("season_id", season_id).execute()

        added_count = 0
        for team in table_data:
            supabase.table("teams").insert({
                "season_id": season_id,
                "team_name": team["teamName"],
                "logo_url": team.get("teamIconUrl", "")
            }).execute()
            added_count += 1

        st.success(f"✅ {added_count} Teams von OpenLigaDB geladen!")
        st.rerun()
    except Exception as e:
        st.error(f"Fehler beim Laden von OpenLigaDB: {str(e)}")


def get_draft_stage(season_id):
    """Holt den aktuellen Draft-Status (waiting/drawing/team_draft/completed)."""
    try:
        result = supabase.table("seasons").select("draft_stage").eq("id", season_id).single().execute()
        return result.data.get("draft_stage", "waiting") if result.data else "waiting"
    except Exception:
        return "waiting"


def update_draft_stage(season_id, stage):
    """Setzt den Draft-Status."""
    try:
        supabase.table("seasons").update({"draft_stage": stage}).eq("id", season_id).execute()
    except Exception as e:
        st.error(f"Fehler beim Aktualisieren des Draft-Status: {str(e)}")


def get_draft_order(season_id):
    """Holt die ausgeloste Reihenfolge (Liste von Spieler-Indizes 1-4) als JSON."""
    try:
        result = supabase.table("seasons").select("draft_order").eq("id", season_id).single().execute()
        if result.data and result.data.get("draft_order"):
            return json.loads(result.data["draft_order"])
        return None
    except Exception:
        return None


def save_draft_order(season_id, draft_order):
    """Speichert die ausgeloste Reihenfolge als JSON-String."""
    try:
        supabase.table("seasons").update({
            "draft_order": json.dumps(draft_order)
        }).eq("id", season_id).execute()
    except Exception as e:
        st.error(f"Fehler beim Speichern der Reihenfolge: {str(e)}")


def complete_draft(season_id):
    """Markiert den Draft als abgeschlossen."""
    try:
        supabase.table("seasons").update({
            "draft_completed": True,
            "draft_stage": "completed"
        }).eq("id", season_id).execute()
    except Exception as e:
        st.error(f"Fehler beim Abschließen des Drafts: {str(e)}")


def get_draft_picks(season_id):
    """Holt alle bisherigen Draft-Picks einer Saison, sortiert nach Pick-Reihenfolge."""
    try:
        result = supabase.table("draft_picks").select("*").eq("season_id", season_id).order("pick_order").execute()
        return result.data if result.data else []
    except Exception:
        return []


def save_draft_pick(season_id, player_id, team_id, pick_order):
    """Speichert einen einzelnen Draft-Pick."""
    try:
        supabase.table("draft_picks").insert({
            "season_id": season_id,
            "player_id": player_id,
            "team_id": team_id,
            "pick_order": pick_order,
            "created_at": datetime.now().isoformat()
        }).execute()
    except Exception as e:
        st.error(f"Fehler beim Speichern des Picks: {str(e)}")


def delete_last_pick(season_id, draft_picks):
    """Löscht den letzten Pick (für Fehlkorrekturen)."""
    if not draft_picks:
        return
    try:
        last_pick = draft_picks[-1]
        supabase.table("draft_picks").delete().eq("id", last_pick["id"]).execute()
    except Exception as e:
        st.error(f"Fehler beim Löschen: {str(e)}")


def reset_draft(season_id):
    """Setzt den kompletten Draft zurück (Picks löschen, Status auf waiting)."""
    try:
        supabase.table("draft_picks").delete().eq("season_id", season_id).execute()
        supabase.table("seasons").update({
            "draft_order": None,
            "draft_stage": "waiting",
            "draft_completed": False
        }).eq("id", season_id).execute()
    except Exception as e:
        st.error(f"Fehler beim Zurücksetzen: {str(e)}")


# ============================================================
# HILFSFUNKTIONEN: Draft-Picks in Tipp-Format umwandeln (Option A)
# ============================================================

def get_snake_pick_order(draft_order, snake_pattern):
    """
    Wandelt die ausgeloste Position (1-4) und das Snake-Muster in eine
    Liste von Spieler-Positionen um, die die Pick-Reihenfolge festlegt.

    draft_order: z.B. [3, 1, 4, 2] -> Position 1 im Draft sitzt Spieler-Index 3, usw.
    snake_pattern: "1234432112344321" -> Reihenfolge der Positionen (nicht Spieler!)

    Rückgabe: Liste von Spieler-Indizes in der Reihenfolge, in der gepickt wird.
    """
    pick_sequence = []
    for position_char in snake_pattern:
        position = int(position_char)  # z.B. 1, 2, 3 oder 4
        spieler_index = draft_order[position - 1]  # welcher Spieler sitzt auf dieser Position
        pick_sequence.append(spieler_index)
    return pick_sequence


def build_current_season_tipps(season_id, players, all_teams):
    """
    Baut aus den Draft-Picks in Supabase ein Dictionary im gleichen Format
    wie tipps_dict, aber nur für die aktuelle Saison.

    Rückgabe: { "Spielername": ["TeamKurzname1", "TeamKurzname2", ...] }
    """
    draft_picks = get_draft_picks(season_id)
    if not draft_picks:
        return {}

    # Nachschlage-Tabellen vorbereiten
    player_lookup = {p["id"]: p["name"] for p in players}
    team_lookup = {t["id"]: t["team_name"] for t in all_teams}

    ergebnis = {}
    for pick in draft_picks:
        spieler_name = player_lookup.get(pick["player_id"])
        team_name_voll = team_lookup.get(pick["team_id"])

        if not spieler_name or not team_name_voll:
            continue

        # Fuzzy-Matching: vollen Namen von OpenLigaDB auf unseren Kurznamen mappen
        kurzname = match_team_to_kurzname(team_name_voll)

        if spieler_name not in ergebnis:
            ergebnis[spieler_name] = []
        ergebnis[spieler_name].append(kurzname)

    return ergebnis


def match_team_to_kurzname(team_name_voll):
    """
    Sucht im teams_info-Dict nach einem passenden Kurznamen für den vollen
    OpenLigaDB-Teamnamen (z.B. 'FC Bayern München' -> 'Bayern').
    Fällt auf den vollen Namen zurück, falls kein Match gefunden wird.
    """
    for kurzname in teams_info:
        if kurzname.lower() in team_name_voll.lower():
            return kurzname
    # Kein Match gefunden -> voller Name wird direkt verwendet
    return team_name_voll


# ============================================================
# DRAFT-UI (Auslosung + Snake-Draft)
# ============================================================

def show_draft_section(season_id, season_year):
    """Zeigt den kompletten Draft-Ablauf: Auslosung -> Snake-Draft -> Fertig."""

    st.markdown('<a id="draft"></a>', unsafe_allow_html=True)
    st.markdown("<hr><br>", unsafe_allow_html=True)
    st.markdown("""
    <div style="background-color:#f5f5f5; padding:15px; border-radius:10px; margin-bottom:15px;">
        <h3>🎲 Team-Draft neue Saison</h3>
    </div>
    """, unsafe_allow_html=True)

    players = get_players()
    if not players:
        st.warning("⚠️ Keine Spieler in der Datenbank vorhanden.")
        return

    player_names = [p["name"] for p in players]
    draft_stage = get_draft_stage(season_id)

    # --- PHASE 1: Auslosung der Positionen ---
    if draft_stage == "waiting":
        st.info("⏳ Die Draft-Reihenfolge wurde noch nicht ausgelost.")
        if st.button("🎰 Positionen jetzt auslosen", key="draw_positions"):
            # Zufällige Reihenfolge der Spieler-Indizes (1-basiert)
            positionen = list(range(1, len(players) + 1))
            random.shuffle(positionen)
            save_draft_order(season_id, positionen)
            update_draft_stage(season_id, "drawing")
            st.rerun()
        return

    draft_order = get_draft_order(season_id)

    # --- PHASE 2: Reihenfolge anzeigen, Start bestätigen ---
    if draft_stage == "drawing":
        st.success("✅ Reihenfolge wurde ausgelost!")
        st.write("**Draft-Positionen:**")
        for i, spieler_index in enumerate(draft_order, 1):
            st.write(f"**Position {i}:** {player_names[spieler_index - 1]}")

        if st.button("➡️ Draft jetzt starten", key="start_team_draft"):
            update_draft_stage(season_id, "team_draft")
            st.rerun()
        return

    # --- PHASE 3: Snake-Draft läuft ---
    if draft_stage == "team_draft":
        all_teams = get_teams_for_season(season_id)

        if not all_teams:
            st.warning("⚠️ Für diese Saison sind noch keine Teams in der Datenbank.")
            if st.button("🔄 Teams von OpenLigaDB laden", key="load_teams_draft"):
                load_teams_from_openligadb(season_year, season_id)
            return

        draft_picks = get_draft_picks(season_id)
        pick_sequence = get_snake_pick_order(draft_order, DRAFT_SNAKE_ORDER)
        gesamt_picks = len(pick_sequence)
        aktueller_pick_nr = len(draft_picks) + 1

        # Übersicht der Reihenfolge anzeigen
        with st.expander("📋 Komplette Pick-Reihenfolge anzeigen", expanded=False):
            for i, spieler_index in enumerate(pick_sequence, 1):
                status = "✅" if i < aktueller_pick_nr else ("▶️ **JETZT**" if i == aktueller_pick_nr else "⏳")
                st.write(f"{status} Pick {i}: {player_names[spieler_index - 1]}")

        st.write("---")

        # Verfügbare Teams berechnen
        gepickte_team_ids = [p["team_id"] for p in draft_picks]
        verfuegbare_teams = [t for t in all_teams if t["id"] not in gepickte_team_ids]

        if aktueller_pick_nr > gesamt_picks:
            st.success("🎉 Draft abgeschlossen! Alle 16 Picks sind erfolgt.")
            if st.button("✅ Draft final abschließen", key="finish_draft"):
                complete_draft(season_id)
                st.rerun()
            return

        aktueller_spieler_index = pick_sequence[aktueller_pick_nr - 1]
        aktueller_spieler_name = player_names[aktueller_spieler_index - 1]

        st.info(f"🎯 **Pick {aktueller_pick_nr} von {gesamt_picks}** – {aktueller_spieler_name} ist an der Reihe")

        # Verfügbare Teams mit Logo anzeigen
        st.write("**Verfügbare Teams:**")
        cols = st.columns(6)
        for idx, team in enumerate(verfuegbare_teams):
            with cols[idx % 6]:
                if team.get("logo_url"):
                    st.image(team["logo_url"], width=50)
                st.caption(team["team_name"])

        st.write("---")

        # Auswahl-Feld für den Pick
        team_options = {t["id"]: t["team_name"] for t in verfuegbare_teams}
        selected_team_id = st.selectbox(
            "Team auswählen:",
            options=list(team_options.keys()),
            format_func=lambda x: team_options[x],
            key=f"team_select_{aktueller_pick_nr}"
        )

        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Team picken", key="confirm_pick"):
                # Spieler-ID in Supabase finden
                spieler_id = next(p["id"] for p in players if p["name"] == aktueller_spieler_name)
                save_draft_pick(season_id, spieler_id, selected_team_id, aktueller_pick_nr)
                st.success(f"✅ {aktueller_spieler_name} hat {team_options[selected_team_id]} gepickt!")
                st.rerun()

        with col2:
            if st.button("🗑️ Letzten Pick korrigieren", key="undo_pick"):
                delete_last_pick(season_id, draft_picks)
                st.warning("🗑️ Letzter Pick wurde gelöscht.")
                st.rerun()

        return

    # --- PHASE 4: Fertig ---
    if draft_stage == "completed":
        st.success("✅ Der Draft für diese Saison ist abgeschlossen!")
        draft_picks = get_draft_picks(season_id)
        all_teams = get_teams_for_season(season_id)
        team_lookup = {t["id"]: t["team_name"] for t in all_teams}
        player_lookup = {p["id"]: p["name"] for p in players}

        st.write("**Finale Draft-Ergebnisse:**")
        for pick in draft_picks:
            spieler_name = player_lookup.get(pick["player_id"], "?")
            team_name = team_lookup.get(pick["team_id"], "?")
            st.write(f"**{spieler_name}** → {team_name}")

        with st.expander("⚠️ Draft zurücksetzen (Vorsicht!)", expanded=False):
            if st.button("🔄 Draft komplett neu starten", key="reset_draft_button"):
                reset_draft(season_id)
                st.warning("🔄 Draft wurde zurückgesetzt.")
                st.rerun()


# ============================================================
# HAUPT-APP
# ============================================================

def show_app():
    st.set_page_config(page_title="⚽ Bundesliga Tippspiel Champs", layout="centered")
    st.title("⚽ Bundesliga Tippspiel Champs")

    # --- Shortcut-Menü ---
    st.sidebar.markdown("### ⚡ Quick Links")
    st.sidebar.markdown("""
    - [🎲 Draft](#draft)
    - [🏆 Rangliste](#rangliste)
    - [📋 Einzelteams](#einzelteams)
    - [💸 Einsatz-Regeln](#einsatzregeln)
    - [⭐ Top-6 Tipps](#top6tipps)
    - [🏆 Bundesliga Top-6](#bundesligatop6)
    - [🏅 Bestenliste](#bestenliste)
    - [📊 Statistik](#statistik)
    """, unsafe_allow_html=True)

    # --- Neue Saison in Supabase sicherstellen ---
    season_row = get_or_create_season(AKTUELLE_SAISON_NAME)
    season_id = season_row["id"]

    # --- Saisonwahl: Startwert = aktuelle Saison ---
    if "season_index" not in st.session_state:
        st.session_state.season_index = AKTUELLE_SAISON_KEY

    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("⬅️ vorherige Saison"):
            st.session_state.season_index = max(1, st.session_state.season_index - 1)
    with col3:
        if st.button("➡️ nächste Saison"):
            st.session_state.season_index = min(max(season_dict.keys()), st.session_state.season_index + 1)

    season_key = st.session_state.season_index
    season = season_dict[season_key]

    st.write(f"**Aktuelle Saison:** Bundesliga {season}")
    st.write(f"**Saison im Tippspiel:** {season_key}")

    # --- Draft-Bereich nur bei der aktuellen (neuen) Saison anzeigen ---
    if season_key == AKTUELLE_SAISON_KEY:
        show_draft_section(season_id, 2026)

        # Prüfen, ob Draft fertig ist -> Tipps dynamisch aus Supabase aufbauen
        draft_stage = get_draft_stage(season_id)
        if draft_stage == "completed":
            players = get_players()
            all_teams = get_teams_for_season(season_id)
            aktuelle_tipps = build_current_season_tipps(season_id, players, all_teams)
            if aktuelle_tipps:
                tipps_dict[AKTUELLE_SAISON_KEY] = aktuelle_tipps
        else:
            # Solange der Draft nicht fertig ist, gibt's noch keine Auswertung
            st.info("ℹ️ Die Saisonübersicht erscheint, sobald der Draft abgeschlossen ist.")
            return

    # --- Tabelle laden über API ---
    url = season_api_urls[season_key]
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        df = pd.DataFrame([{
            "Team": team["teamName"],
            "Kurzname": team.get("shortName", ""),
            "Punkte": team["points"],
            "Sp.": team["matches"],
            "Siege": team["won"],
            "Unentschieden": team["draw"],
            "Niederlagen": team["lost"],
            "Tordifferenz": team["goalDiff"]
        } for team in data])
    else:
        st.error(f"Die Tabelle konnte nicht geladen werden. Status Code: {response.status_code}")
        return

    # --- Punkteberechnung ---
    def berechne_punkte_und_spiele(liste):
        gesamtpunkte, gesamtspiele = 0, 0
        punkte_teams = []
        for team in liste:
            team_data = df.loc[df['Team'].str.contains(team, case=False), ['Team', 'Punkte', 'Sp.']]
            if not team_data.empty:
                punkte = int(team_data['Punkte'].iloc[0])
                gesamtpunkte += punkte
                gesamtspiele += int(team_data['Sp.'].iloc[0])
                punkte_teams.append((team, punkte))
            else:
                punkte_teams.append((team, 0))
        return gesamtpunkte, gesamtspiele, punkte_teams

    listen = tipps_dict.get(season_key, {})
    if not listen:
        st.warning("⚠️ Für diese Saison liegen noch keine Tipps vor.")
        return

    ergebnisse = {name: berechne_punkte_und_spiele(liste) for name, liste in listen.items()}

    # --- Abstand und Linie ---
    st.markdown("<hr><br>", unsafe_allow_html=True)

    # --- Rangliste ---
    st.markdown('<a id="rangliste"></a>', unsafe_allow_html=True)
    st.markdown("""
    <h3 style='border-left:5px solid #ff4d4d; padding-left:10px;'>🏆 Rangliste</h3>
    """, unsafe_allow_html=True)

    punkte_df = pd.DataFrame(
        [(name, daten[0], daten[1]) for name, daten in ergebnisse.items()],
        columns=['Name', 'Punkte', 'Sp.']
    )
    punkte_df = punkte_df.sort_values('Punkte', ascending=True).reset_index(drop=True)
    punkte_df['Platzierung'] = range(1, len(punkte_df) + 1)
    punkte_df = punkte_df[['Platzierung', 'Name', 'Punkte', 'Sp.']].copy()
    punkte_df = punkte_df.rename(columns={'Sp.': 'Spiele'})

    def render_rangliste(df):
        html = "<table style='border-collapse:collapse; width:100%;'>"
        html += "<tr style='background-color:#ffffff; text-align:center; font-weight:bold;'>"
        html += "<th>Platz</th><th>Name</th><th>Punkte</th><th>Spiele</th></tr>"

        for i, row in df.iterrows():
            bg_color = "#ffffff" if i % 2 == 0 else "#f9f9f9"
            platz = row['Platzierung']
            if platz == 1:
                platz_text = f"🥇 {platz}"
            elif platz == 2:
                platz_text = f"🥈 {platz}"
            elif platz == 3:
                platz_text = f"🥉 {platz}"
            elif platz == 4:
                platz_text = f"🪵 {platz}"
            else:
                platz_text = str(platz)

            html += f"<tr style='background-color:{bg_color}; text-align:center;'>"
            html += f"<td>{platz_text}</td><td style='text-align:left; padding-left:10px;'>{row['Name']}</td>"
            html += f"<td>{row['Punkte']}</td><td>{row['Spiele']}</td>"
            html += "</tr>"

        html += "</table>"
        return html

    st.markdown(render_rangliste(punkte_df), unsafe_allow_html=True)

    # --- Abstand und Linie ---
    st.markdown("<hr><br>", unsafe_allow_html=True)

    # --- Einzelteams ---
    st.markdown('<a id="einzelteams"></a>', unsafe_allow_html=True)
    farben = {'Paul': '#e6f7ff', 'Tuschi': '#fff0e6', 'Choci': '#f9f0ff', 'Dan': '#e6ffe6'}
    st.markdown("""
    <div style="background-color:#f5f5f5; padding:15px; border-radius:10px; box-shadow: 2px 2px 5px rgba(0,0,0,0.1); margin-bottom:15px;">
        <h3>📋 Punkte der Einzelteams</h3>
    </div>
    """, unsafe_allow_html=True)
    zeilen_hoehe = 40
    logo_hoehe = 25
    logo_breite_max = 70

    def render_team_zeile(team_kurzname, punkte_text=None):
        """Baut eine Zeile mit Logo + Name (+ optional Punkte) fürs Einzelteam-Layout."""
        info = teams_info.get(team_kurzname, {"name": team_kurzname, "logo": ""})
        team_name = info["name"]
        logo_path = info["logo"]

        if logo_path and Path(logo_path).exists():
            img = Image.open(logo_path)
            w, h = img.size
            neu_w = int((logo_hoehe / h) * w)
            img = img.resize((neu_w, logo_hoehe))
            buffered = BytesIO()
            img.save(buffered, format="PNG")
            img_b64 = base64.b64encode(buffered.getvalue()).decode()
            logo_html = f"<img src='data:image/png;base64,{img_b64}' height='{logo_hoehe}px' style='display:block; margin:auto;'>"
        else:
            logo_html = ""

        punkte_html = f"<div style='flex:1; text-align:right; white-space: nowrap;'>{punkte_text}</div>" if punkte_text else ""

        return f"""
        <div style='display:flex; align-items:center; height:{zeilen_hoehe}px; padding:2px 0;'>
            <div style='width:{logo_breite_max}px; display:flex; justify-content:center;'>{logo_html}</div>
            <div style='flex:4; padding-left:5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;'>{team_name}</div>
            {punkte_html}
        </div>
        """

    for name, daten in ergebnisse.items():
        st.markdown(f"**{name}**")
        st.markdown(f'<div style="background-color:{farben.get(name, "white")}; padding:5px; border-radius:5px;">', unsafe_allow_html=True)
        for team, punkte in daten[2]:
            st.markdown(render_team_zeile(team, f"{punkte} Punkte"), unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # --- Abstand und Linie ---
    st.markdown("<hr><br>", unsafe_allow_html=True)

    # --- Einsatz-Text ---
    st.markdown('<a id="einsatzregeln"></a>', unsafe_allow_html=True)
    st.markdown("""
    ### 💸 Einsatz-Regeln
    - **4. Platz** → 3 Runden zahlen  
    - **3. Platz** → 2 Runden zahlen  
    - **2. Platz** → 1 Runde zahlen  

    ⚠️ Bei **Punktgleichheit** zahlen die den Abend!  
    🎰 Bei **3 oder 4 Punktgleichen** geht's ins **Casino**!
    """)

    # --- Top-6 Tipps (nur für alte Saisons vorhanden) ---
    st.markdown('<a id="top6tipps"></a>', unsafe_allow_html=True)
    st.markdown("<hr><br>", unsafe_allow_html=True)
    st.markdown("""
    <div style="background-color:#f5f5f5; padding:15px; border-radius:10px; box-shadow: 2px 2px 5px rgba(0,0,0,0.1); margin-bottom:15px;">
        <h3>⭐ Top-6 Tipps der Bundesliga</h3>
    </div>
    """, unsafe_allow_html=True)

    if season_key in top6_tipps:
        personen = list(top6_tipps[season_key].keys())
        for name in personen:
            st.markdown(f"**{name}**")
            st.markdown(f'<div style="background-color:{farben.get(name, "white")}; padding:5px; border-radius:5px;">', unsafe_allow_html=True)
            teams = top6_tipps.get(season_key, {}).get(name, [])
            for team in teams:
                st.markdown(render_team_zeile(team), unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("ℹ️ Für diese Saison liegen noch keine Top-6-Tipps vor.")

    # --- Bundesliga Top-6 Tabelle ---
    st.markdown('<a id="bundesligatop6"></a>', unsafe_allow_html=True)
    st.markdown("<hr><br>", unsafe_allow_html=True)
    st.subheader(f"🏆 Bundesliga Top-6 Saison - {season}")

    try:
        top6_df = df.head(6).copy()
        for i, row in top6_df.iterrows():
            team_name_lookup = next(
                (key for key in teams_info if key.lower() in row['Team'].lower()),
                None
            )
            info = teams_info.get(team_name_lookup, {"name": row['Team'], "logo": ""})
            team_name = info["name"]
            logo_path = info["logo"]

            if logo_path and Path(logo_path).exists():
                img = Image.open(logo_path)
                w, h = img.size
                neu_w = int((logo_hoehe / h) * w)
                img = img.resize((neu_w, logo_hoehe))
                buffered = BytesIO()
                img.save(buffered, format="PNG")
                img_b64 = base64.b64encode(buffered.getvalue()).decode()
                logo_html = f"<img src='data:image/png;base64,{img_b64}' height='{logo_hoehe}px' style='display:block; margin:auto;'>"
            else:
                logo_html = ""

            st.markdown(
                f"""
                <div style='display:flex; align-items:center; height:{zeilen_hoehe}px; padding:2px 0; border-bottom:1px solid #f0f0f0;'>
                    <div style='width:{logo_breite_max}px; display:flex; justify-content:center;'>{logo_html}</div>
                    <div style='flex:4; padding-left:5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;'>{team_name}</div>
                    <div style='flex:1; text-align:right; white-space: nowrap;'>{row['Punkte']} Punkte</div>
                </div>
                """,
                unsafe_allow_html=True
            )
    except Exception as e:
        st.error(f"Die Top-6 Tabelle konnte nicht geladen werden: {e}")

    # --- Abstand und Linie ---
    st.markdown("<hr><br>", unsafe_allow_html=True)

    # --- Bestenliste ---
    st.markdown('<a id="bestenliste"></a>', unsafe_allow_html=True)
    st.markdown("""
    <div style="border: 2px solid #ccc; padding:15px; border-radius:10px; margin-bottom:15px;">
        <h3>🏅 Bestenliste</h3>
    </div>
    """, unsafe_allow_html=True)

    def erstelle_bestenliste(saison_keys, titel, platz4_holz=False):
        gesamtpunkte = {}
        for key in saison_keys:
            listen_key = tipps_dict.get(key, {})
            url_key = season_api_urls.get(key)
            if not url_key or not listen_key:
                continue

            response = requests.get(url_key)
            if response.status_code != 200:
                st.error(f"Bestenliste: Tabelle für Saison {season_dict[key]} konnte nicht geladen werden.")
                continue

            data_key = response.json()
            df_saison = pd.DataFrame([{
                "Team": team["teamName"],
                "Punkte": team["points"]
            } for team in data_key])

            for name, teams in listen_key.items():
                if name not in gesamtpunkte:
                    gesamtpunkte[name] = 0
                for team in teams:
                    team_data = df_saison.loc[df_saison['Team'].str.contains(team, case=False), 'Punkte']
                    if not team_data.empty:
                        gesamtpunkte[name] += int(team_data.iloc[0])

        if not gesamtpunkte:
            return

        best_df = pd.DataFrame(
            [(name, punkte) for name, punkte in gesamtpunkte.items()],
            columns=['Name', 'Punkte']
        )
        best_df = best_df.sort_values('Punkte', ascending=True).reset_index(drop=True)
        best_df['Platzierung'] = range(1, len(best_df) + 1)
        best_df = best_df[['Platzierung', 'Name', 'Punkte']]

        best_df_display = best_df.copy()

        def emoji_top4(p):
            if p == 1: return f"🥇 {p}"
            elif p == 2: return f"🥈 {p}"
            elif p == 3: return f"🥉 {p}"
            elif p == 4 and platz4_holz: return f"🪵 {p}"
            else: return str(p)

        best_df_display['Platzierung'] = best_df_display['Platzierung'].apply(emoji_top4)

        def highlight_top4_bl(row):
            platz = int(''.join(filter(str.isdigit, str(row['Platzierung']))))
            if platz == 1:
                return ['background-color:#fff9e6; font-weight:bold; text-align:center'] * len(row)
            elif platz == 2:
                return ['background-color:#f2f2f2; font-weight:bold; text-align:center'] * len(row)
            elif platz == 3:
                return ['background-color:#f7e6d9; font-weight:bold; text-align:center'] * len(row)
            elif platz == 4 and platz4_holz:
                return ['background-color:#e6f0ff; font-weight:bold; text-align:center'] * len(row)
            else:
                return [''] * len(row)

        st.markdown(f"### {titel}")
        st.dataframe(best_df_display.style.apply(highlight_top4_bl, axis=1), use_container_width=True, hide_index=True)

    erstelle_bestenliste([1, 2], "Beste 3 Personen (Saison 2022-23 & 2023-24)")

    spaetere_saisons = [k for k in season_dict if k >= 3]
    erstelle_bestenliste(spaetere_saisons, "Beste 4 Personen (Saison ab 2024-25)", platz4_holz=True)

    # --- Abstand und Linie ---
    st.markdown("<hr><br>", unsafe_allow_html=True)

    # --- Statistik: Wie oft welcher Verein gewählt ---
    st.markdown('<a id="statistik"></a>', unsafe_allow_html=True)
    st.markdown("""
    <div style="border: 2px solid #ccc; padding:15px; border-radius:10px; margin-bottom:15px;">
        <h3>📊 Statistik: Anzahl Tipps pro Verein</h3>
    </div>
    """, unsafe_allow_html=True)

    alle_personen = set()
    for key in tipps_dict:
        alle_personen.update(tipps_dict[key].keys())

    statistik_dict = {name: {} for name in alle_personen}

    for key in tipps_dict:
        listen_key = tipps_dict[key]
        for name, teams in listen_key.items():
            for team in teams:
                statistik_dict[name][team] = statistik_dict[name].get(team, 0) + 1

    zeilen_hoehe_stat = 35

    for name, teams_count in statistik_dict.items():
        if not teams_count:
            continue
        st.markdown(f"**{name}**")
        st.markdown(f'<div style="background-color:{farben.get(name, "white")}; padding:5px; border-radius:5px;">', unsafe_allow_html=True)

        sorted_teams = sorted(teams_count.items(), key=lambda x: x[1], reverse=True)

        for team, anzahl in sorted_teams:
            info = teams_info.get(team, {"name": team, "logo":            ""})
            team_name = info["name"]
            logo_path = info["logo"]

            if logo_path and Path(logo_path).exists():
                img = Image.open(logo_path)
                w, h = img.size
                neu_w = int((logo_hoehe / h) * w)
                img = img.resize((neu_w, logo_hoehe))
                buffered = BytesIO()
                img.save(buffered, format="PNG")
                img_b64 = base64.b64encode(buffered.getvalue()).decode()
                logo_html = f"<img src='data:image/png;base64,{img_b64}' height='{logo_hoehe}px' style='display:block; margin:auto;'>"
            else:
                logo_html = ""

            st.markdown(
                f"""
                <div style='display:flex; align-items:center; height:{zeilen_hoehe_stat}px; padding:2px 0;'>
                    <div style='width:{logo_breite_max}px; display:flex; justify-content:center;'>{logo_html}</div>
                    <div style='flex:4; padding-left:5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;'>{team_name}</div>
                    <div style='flex:1; text-align:right; white-space: nowrap;'>{anzahl}x</div>
                </div>
                """,
                unsafe_allow_html=True
            )

        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<br><hr>", unsafe_allow_html=True)
    st.info("✅ Diese App ist open source und wird ständig weiterentwickelt. Feedback ist willkommen!")


# ============================================================
# AUTH + HAUPT-EINSTIEG
# ============================================================

def main():
    """Einstiegspunkt mit Password-Schutz."""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.set_page_config(page_title="⚽ Bundesliga Tippspiel Champs", layout="centered")
        st.title("🔒 Bundesliga Tippspiel")
        st.write("Bitte melde dich an:")

        password = st.text_input("Passwort:", type="password")

        if st.button("🔓 Anmelden"):
            if password == PASSWORT:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("❌ Falsches Passwort!")
    else:
        show_app()


if __name__ == "__main__":
    main()
