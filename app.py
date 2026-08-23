import streamlit as st
import random
import json
import requests
from supabase import create_client, Client
from datetime import datetime

# --- KONFIGURATION ---
SUPABASE_URL = st.secrets["supabase_url"]
SUPABASE_KEY = st.secrets["supabase_key"]
AKTUELLE_SAISON = "2026/2027"

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
        "is_active": True,
        "draft_status": "waiting"
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

def load_teams_from_openligadb(season_year):
    """Lädt Teams von OpenLigaDB und speichert sie in der DB."""
    try:
        url = f"https://api.openligadb.de/getbltable/bl1/{season_year}"
        response = requests.get(url)
        response.raise_for_status()
        
        table_data = response.json()
        
        added_count = 0
        
        for team in table_data:
            # Prüfe, ob Team bereits existiert
            existing = supabase.table("teams").select("*").eq("team_name", team["teamName"]).eq("season_id", season_id).execute()
            
            if not existing.data:
                supabase.table("teams").insert({
                    "season_id": season_id,
                    "team_name": team["teamName"],
                    "logo_url": team.get("teamIconUrl", "⚽")
                }).execute()
                added_count += 1
        
        if added_count > 0:
            st.success(f"✅ {added_count} neue Teams geladen!")
        else:
            st.info("ℹ️ Alle Teams sind bereits in der DB.")
        st.rerun()
    except Exception as e:
        st.error(f"Fehler beim Laden von OpenLigaDB: {str(e)}")

# --- HAUPTAPP ---

st.set_page_config(page_title="⚽ Bundesliga Tippspiel 2.0", layout="wide")
st.title("⚽ Bundesliga Tippspiel 2.0")

# Saison initialisieren
season = get_or_create_season(AKTUELLE_SAISON)
season_id = season["id"]

# Spieler laden
players = get_players()
player_names = [p["name"] for p in players] if players else []

# --- SPIELER AUSWÄHLEN ---
st.sidebar.subheader("👤 Dein Profil")
current_player = st.sidebar.selectbox(
    "Wähle deinen Namen:",
    player_names if player_names else ["Keine Spieler vorhanden"]
)

# Admin-Check
is_admin = current_player == "Choci"

# UI für Admin vs. Zuschauer
if is_admin:
    st.sidebar.success(f"✅ Du bist Admin!")
else:
    st.sidebar.info(f"👀 Du beobachtest als {current_player}")

# Draft-Status laden
draft_status = get_draft_status(season_id)

# --- ADMIN-BEREICH ---
if is_admin:
    with st.sidebar.expander("🔧 Admin-Panel", expanded=False):
        admin_tab1, admin_tab2 = st.tabs(["👥 Spieler", "⚽ Teams"])
        
        with admin_tab1:
            st.subheader("Spieler verwalten")
            new_player_name = st.text_input("Neuer Spieler:", key="new_player_input")
            if st.button("➕ Spieler hinzufügen"):
                if new_player_name:
                    try:
                        supabase.table("players").insert({"name": new_player_name}).execute()
                        st.success(f"✅ {new_player_name} hinzugefügt!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Fehler: {str(e)}")
                else:
                    st.warning("Bitte Namen eingeben!")
        
        with admin_tab2:
            st.subheader("Teams verwalten")
            
            if st.button("🔄 Teams von OpenLigaDB laden (2026)"):
                load_teams_from_openligadb(2026)
            
            st.write("---")
            st.write("**Manuell hinzufügen:**")
            col1, col2 = st.columns(2)
            
            with col1:
                team_name = st.text_input("Team-Name:", key="manual_team_name")
            with col2:
                logo_url = st.text_input("Logo-URL:", key="manual_logo_url")
            
            if st.button("➕ Team manuell hinzufügen"):
                if team_name and logo_url:
                    try:
                        supabase.table("teams").insert({
                            "season_id": season_id,
                            "team_name": team_name,
                            "logo_url": logo_url
                        }).execute()
                        st.success(f"✅ {team_name} hinzugefügt!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Fehler: {str(e)}")
                else:
                    st.warning("Bitte Team-Name und Logo eingeben!")

# --- HAUPTBEREICH DER APP ---

if draft_status == "waiting":
    st.subheader("🎲 Draft-Reihenfolge auslosen")
    
    if not players:
        st.warning("⚠️ Keine Spieler in der Datenbank. Bitte zuerst Spieler hinzufügen!")
    else:
        if is_admin:
            if st.button("🎰 Reihenfolge auslosen", key="draw_button"):
                draft_order = list(range(1, len(players) + 1))
                random.shuffle(draft_order)
                save_draft_order(season_id, draft_order)
                update_draft_status(season_id, "drawing")
                st.rerun()
        else:
            st.info("⏳ Warte darauf, dass Choci die Reihenfolge auslost...")

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
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Reihenfolge neu auslosen", key="redraw_button"):
                draft_order = list(range(1, len(players) + 1))
                random.shuffle(draft_order)
                save_draft_order(season_id, draft_order)
                st.rerun()
        
        with col2:
            if st.button("▶️ Team-Draft starten", key="start_team_draft"):
                update_draft_status(season_id, "team_draft")
                st.rerun()
    else:
        st.info("⏳ Warte darauf, dass Choci den Team-Draft startet...")

elif draft_status == "team_draft":
    st.subheader("🏆 Team-Draft")
    
    draft_order = get_draft_order(season_id)
    draft_picks = get_draft_picks(season_id)
    
    # Bestimme aktuelle Pick-Nummer
    current_pick_number = len(draft_picks) + 1
    players_count = len(players)
    
    # Zeige aktuelle Reihenfolge
    st.write("---")
    st.write("**Draft-Reihenfolge:**")
    for i, pos in enumerate(draft_order[:players_count], 1):
        player_name = player_names[pos-1]
        status = "✅" if i < current_pick_number else ("▶️ **AKTIV**" if i == current_pick_number else "⏳")
        st.write(f"{status} Pick {i}: {player_name}")
    st.write("---")
    
    # Nur der aktuelle Spieler kann ein Team picken
    current_pick_player_pos = draft_order[current_pick_number - 1] if current_pick_number <= players_count else None
    current_pick_player_name = player_names[current_pick_player_pos - 1] if current_pick_player_pos else None
    
    if current_pick_number <= players_count:
        if current_player == current_pick_player_name:
            st.info(f"🎯 Du bist an der Reihe! Pick {current_pick_number}")
            
            # Hole verfügbare Teams
            all_teams = get_teams_for_season(season_id)
            picked_team_ids = [p["team_id"] for p in draft_picks]
            available_teams = [t for t in all_teams if t["id"] not in picked_team_ids]
            
            if not all_teams:
                st.warning("⚠️ Keine Teams in der Datenbank! Bitte zuerst Teams hinzufügen (Admin-Bereich).")
            elif available_teams:
                team_options = {t["id"]: f"{t['logo_url']} {t['team_name']}" for t in available_teams}
                
                selected_team_id = st.selectbox(
                    "Wähle ein Team:",
                    options=list(team_options.keys()),
                    format_func=lambda x: team_options[x],
                    key=f"team_select_{current_pick_number}"
                )
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button(f"✅ Team picken", key="pick_button"):
                        save_draft_pick(season_id, current_pick_player_pos, selected_team_id, current_pick_number)
                        st.success(f"✅ {current_pick_player_name} hat {[t['team_name'] for t in all_teams if t['id'] == selected_team_id][0]} gepickt!")
                        st.rerun()
                
                with col2:
                    if st.button("🗑️ Fehlpick löschen", key="delete_pick"):
                        if len(draft_picks) > 0:
                            last_pick = draft_picks[-1]
                            try:
                                supabase.table("draft_picks").delete().eq("id", last_pick["id"]).execute()
                                st.warning(f"🗑️ Letzter Pick gelöscht!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Fehler beim Löschen: {str(e)}")
            else:
                st.success("🎉 Alle Teams sind gepickt!")
        else:
            st.info(f"⏳ {current_pick_player_name} ist an der Reihe...")
    else:
        st.success("🎉 Draft abgeschlossen!")
    
    # Admin-Optionen
    if is_admin:
        st.write("---")
        st.subheader("🔧 Admin-Optionen")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Draft neu starten", key="restart_draft"):
                try:
                    # Lösche alle Draft-Picks
                    supabase.table("draft_picks").delete().gt("id", 0).eq("season_id", season_id).execute()
                    # Reset Draft-Order
                    update_draft_status(season_id, "waiting")
                    st.warning("🔄 Draft wurde zurückgesetzt!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Fehler beim Zurücksetzen: {str(e)}")
        
        with col2:
            if st.button("✅ Draft abschließen", key="complete_draft"):
                complete_draft(season_id)
                st.success("🎉 Draft abgeschlossen!")
                st.rerun()
