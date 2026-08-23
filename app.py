import streamlit as st
import random
import json
from supabase import create_client, Client
from datetime import datetime

# --- KONFIGURATION ---
SUPABASE_URL = st.secrets["supabase_url"]
SUPABASE_KEY = st.secrets["supabase_key"]
AKTUELLE_SAISON = "2024/2025"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- DATENBANKFUNKTIONEN ---

def get_or_create_season(season_name):
    """Holt oder erstellt eine Saison."""
    try:
        result = supabase.table("seasons").select("*").eq("name", season_name).single().execute()
        if result.data:
            return result.data
    except:
        pass
    
    # Erstelle neue Saison
    new_season = {
        "name": season_name,
        "created_at": datetime.now().isoformat(),
        "draft_status": "waiting",
        "draft_order": None
    }
    result = supabase.table("seasons").insert(new_season).execute()
    return result.data[0] if result.data else new_season

def get_players():
    """Holt alle Spieler aus der DB."""
    try:
        result = supabase.table("players").select("*").execute()
        return result.data if result.data else []
    except:
        return []

def get_teams_for_season(season_id):
    """Holt alle Teams einer Saison."""
    try:
        result = supabase.table("teams").select("*").eq("season_id", season_id).execute()
        return result.data if result.data else []
    except:
        return []

def get_draft_status(season_id):
    """Holt den Draft-Status einer Saison."""
    try:
        result = supabase.table("seasons").select("draft_status").eq("id", season_id).single().execute()
        if result.data:
            return result.data.get("draft_status", "waiting")
        return "waiting"
    except Exception as e:
        st.error(f"Fehler beim Laden des Draft-Status: {str(e)}")
        return "waiting"

def get_draft_order(season_id):
    """Holt die ausgeloste Draft-Reihenfolge."""
    try:
        result = supabase.table("seasons").select("draft_order").eq("id", season_id).single().execute()
        if result.data and result.data.get("draft_order"):
            draft_order_str = result.data.get("draft_order")
            # Versuche JSON zu parsen
            try:
                return json.loads(draft_order_str)
            except:
                # Fallback für alte String-Formatierung
                return [int(d) for d in draft_order_str]
        return None
    except:
        return None

def save_draft_order(season_id, draft_order):
    """Speichert die Draft-Reihenfolge als JSON."""
    try:
        supabase.table("seasons").update({
            "draft_order": json.dumps(draft_order)
        }).eq("id", season_id).execute()
    except Exception as e:
        st.error(f"Fehler beim Speichern der Draft-Reihenfolge: {str(e)}")

def update_draft_status(season_id, status):
    """Aktualisiert den Draft-Status."""
    try:
        supabase.table("seasons").update({
            "draft_status": status
        }).eq("id", season_id).execute()
    except Exception as e:
        st.error(f"Fehler beim Aktualisieren des Draft-Status: {str(e)}")

def complete_draft(season_id):
    """Markiert den Draft als abgeschlossen."""
    update_draft_status(season_id, "completed")

def get_draft_picks(season_id):
    """Holt alle Draft-Picks einer Saison."""
    try:
        result = supabase.table("draft_picks").select("*").eq("season_id", season_id).order("pick_order").execute()
        return result.data if result.data else []
    except:
        return []

def save_draft_pick(season_id, player_id, team_id, pick_order):
    """Speichert einen Draft-Pick."""
    try:
        pick = {
            "season_id": season_id,
            "player_id": player_id,
            "team_id": team_id,
            "pick_order": pick_order,
            "created_at": datetime.now().isoformat()
        }
        supabase.table("draft_picks").insert(pick).execute()
    except Exception as e:
        st.error(f"Fehler beim Speichern des Draft-Picks: {str(e)}")

def get_bundesliga_table():
    """Holt die aktuelle Bundesliga-Tabelle."""
    # Placeholder – hier könnte eine API-Integration folgen
    return None

# --- HAUPTAPP ---

st.set_page_config(page_title="⚽ Bundesliga Tippspiel 2.0", layout="wide")
st.title("⚽ Bundesliga Tippspiel 2.0")

# Saison initialisieren
season = get_or_create_season(AKTUELLE_SAISON)
season_id = season["id"]

# Spieler und Admin-Status laden
players = get_players()
player_names = [p["name"] for p in players] if players else []

# Dummy für Admin-Check (anpassbar)
is_admin = st.secrets.get("admin_user") == st.session_state.get("user", None)

# Draft-Status laden
draft_status = get_draft_status(season_id)

# --- HAUPTBEREICH DER APP ---

if draft_status == "waiting":
    st.subheader("🎲 Draft-Reihenfolge auslosen")
    
    if not players:
        st.warning("⚠️ Keine Spieler in der Datenbank. Bitte zuerst Spieler hinzufügen!")
    else:
        if st.button("Reihenfolge auslosen"):
            draft_order = list(range(1, len(players) + 1))
            random.shuffle(draft_order)
            save_draft_order(season_id, draft_order)  # JSON wird in der Funktion gemacht
            update_draft_status(season_id, "drawing")
            st.rerun()

elif draft_status == "drawing":
    st.success("✅ Draft-Reihenfolge wurde ausgelost!")
    
    draft_order = get_draft_order(season_id)
    
    # Zeige die Draft-Reihenfolge an
    st.subheader("🎲 Draft-Reihenfolge:")
    if draft_order:
        st.write("---")
        col1, col2 = st.columns(2)
        
        with col1:
            for i, pos in enumerate(draft_order[:len(draft_order)//2 + 1], 1):
                st.write(f"**Pick {i}:** {player_names[pos-1]}")
        
        with col2:
            for i, pos in enumerate(draft_order[len(draft_order)//2 + 1:], len(draft_order)//2 + 2):
                st.write(f"**Pick {i}:** {player_names[pos-1]}")
        
        st.write("---")
    
    # Nur Admin kann weiter machen
    if is_admin:
        st.info("📋 Du bist Admin – Starte jetzt den Team-Draft!")
        if st.button("Team-Draft starten"):
            update_draft_status(season_id, "team_draft")
            st.rerun()
    else:
        st.info("⏳ Warte darauf, dass der Admin den Team-Draft startet...")

elif draft_status == "team_draft":
    st.subheader("🏆 Team-Draft")
    st.write("Der Team-Draft läuft... (noch nicht implementiert)")
    
    if is_admin:
        if st.button("Draft abschließen"):
            complete_draft(season_id)
            st.rerun()

elif draft_status == "completed":
    st.success("🎉 Draft abgeschlossen!")
    
    draft_picks = get_draft_picks(season_id)
    if draft_picks:
        st.dataframe(draft_picks)
    else:
        st.info("Noch keine Picks gespeichert.")

else:
    st.warning(f"⚠️ Unbekannter Draft-Status: {draft_status}")
