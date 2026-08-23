import json
import random
from datetime import datetime
from typing import Any

import pandas as pd
import requests
import streamlit as st
from supabase import Client, create_client


# ============================================================
# KONFIGURATION
# ============================================================

st.set_page_config(
    page_title="⚽ Bundesliga Tippspiel",
    page_icon="⚽",
    layout="wide",
)

SUPABASE_URL = st.secrets["supabase_url"]
SUPABASE_KEY = st.secrets["supabase_key"]
ADMIN_USER = st.secrets.get("admin_user", "admin")

AKTUELLE_SAISON = "2026-27"
AKTUELLES_BUNDESLIGA_JAHR = 2026

# Vier Personen, insgesamt 16 Picks
ANZAHL_SPIELER = 4
PICKS_PRO_SPIELER = 4
ANZAHL_PICKS = ANZAHL_SPIELER * PICKS_PRO_SPIELER

# Die eigentliche Reihenfolge der Personen wird später
# zufällig durch die Auslosung bestimmt.
#
# Beispiel:
# Auslosung: Person 3, Person 1, Person 4, Person 2
#
# Dann lautet die Pick-Reihenfolge:
# 3 1 4 2 2 4 1 3 3 1 4 2 2 4 1 3
SNAKE_REIHENFOLGE = [
    0, 1, 2, 3,
    3, 2, 1, 0,
    0, 1, 2, 3,
    3, 2, 1, 0,
]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# ============================================================
# HILFSFUNKTIONEN
# ============================================================

def daten_oder_leere_liste(response: Any) -> list[dict]:
    """Gibt die Daten einer Supabase-Antwort oder eine leere Liste zurück."""
    if response is None or not response.data:
        return []

    if isinstance(response.data, list):
        return response.data

    return [response.data]


def spieler_name(players: list[dict], player_id: int | None) -> str:
    """Ermittelt den Spielernamen anhand der ID."""
    player = next(
        (player for player in players if player["id"] == player_id),
        None,
    )
    return player["name"] if player else "Unbekannt"


def team_name(teams: list[dict], team_id: int | None) -> str:
    """Ermittelt den Teamnamen anhand der ID."""
    team = next(
        (team for team in teams if team["id"] == team_id),
        None,
    )
    return team["team_name"] if team else "Unbekannt"


def erstelle_snake_reihenfolge(auslosung: list[int]) -> list[int]:
    """
    Erstellt aus der ausgelosten Sitzreihenfolge
    die endgültige Reihenfolge mit 16 Picks.

    Beispiel:
    auslosung = [3, 1, 4, 2]

    Ergebnis:
    [3, 1, 4, 2, 2, 4, 1, 3,
     3, 1, 4, 2, 2, 4, 1, 3]
    """
    return [
        auslosung[position]
        for position in SNAKE_REIHENFOLGE
    ]


# ============================================================
# SUPABASE: SAISON
# ============================================================

def get_or_create_season(season_name: str) -> dict:
    """Holt eine Saison oder legt sie neu an."""
    response = (
        supabase
        .table("seasons")
        .select("*")
        .eq("name", season_name)
        .execute()
    )

    if response.data:
        return response.data[0]

    response = (
        supabase
        .table("seasons")
        .insert({
            "name": season_name,
            "is_active": True,
            "draft_order": None,
            "draft_status": "waiting",
        })
        .execute()
    )

    if not response.data:
        raise RuntimeError("Die Saison konnte nicht angelegt werden.")

    return response.data[0]


def get_draft_status(season_id: int) -> str:
    """Lädt den aktuellen Status der Saison."""
    response = (
        supabase
        .table("seasons")
        .select("draft_status")
        .eq("id", season_id)
        .single()
        .execute()
    )

    if response.data:
        return response.data.get("draft_status") or "waiting"

    return "waiting"


def update_draft_status(season_id: int, status: str) -> None:
    """Aktualisiert den Draftstatus."""
    (
        supabase
        .table("seasons")
        .update({"draft_status": status})
        .eq("id", season_id)
        .execute()
    )


# ============================================================
# SUPABASE: SPIELER
# ============================================================

def get_players() -> list[dict]:
    """Lädt alle Spieler."""
    response = (
        supabase
        .table("players")
        .select("*")
        .order("id")
        .execute()
    )

    return daten_oder_leere_liste(response)


# ============================================================
# SUPABASE: TEAMS
# ============================================================

def get_teams_for_season(season_id: int) -> list[dict]:
    """Lädt die Teams der ausgewählten Saison."""
    response = (
        supabase
        .table("teams")
        .select("*")
        .eq("season_id", season_id)
        .order("team_name")
        .execute()
    )

    return daten_oder_leere_liste(response)


# ============================================================
# SUPABASE: DRAFT-REIHENFOLGE
# ============================================================

def get_draft_order(season_id: int) -> list[dict]:
    """
    Lädt die vollständige Draft-Reihenfolge aus der Tabelle draft_order.

    position = 1 bis 16
    player_id = Spieler, der an dieser Position zieht
    """
    response = (
        supabase
        .table("draft_order")
        .select("*")
        .eq("season_id", season_id)
        .order("position")
        .execute()
    )

    return daten_oder_leere_liste(response)


def save_draft_order(
    season_id: int,
    player_ids: list[int],
) -> None:
    """Speichert die vollständigen 16 Draftpositionen."""
    # Sicherheitshalber alte Draftreihenfolge löschen
    (
        supabase
        .table("draft_order")
        .delete()
        .eq("season_id", season_id)
        .execute()
    )

    rows = [
        {
            "season_id": season_id,
            "player_id": player_id,
            "position": position,
        }
        for position, player_id in enumerate(player_ids, start=1)
    ]

    (
        supabase
        .table("draft_order")
        .insert(rows)
        .execute()
    )

    # Zusätzlich speichern wir die Reihenfolge als JSON
    # in seasons.draft_order. Das ist praktisch für spätere
    # Exporte und Rückwärtskompatibilität.
    (
        supabase
        .table("seasons")
        .update({
            "draft_order": json.dumps(player_ids)
        })
        .eq("id", season_id)
        .execute()
    )


def reset_draft_order(season_id: int) -> None:
    """Löscht die gespeicherte Auslosung."""
    (
        supabase
        .table("draft_order")
        .delete()
        .eq("season_id", season_id)
        .execute()
    )

    (
        supabase
        .table("seasons")
        .update({
            "draft_order": None,
            "draft_status": "waiting",
        })
        .eq("id", season_id)
        .execute()
    )


# ============================================================
# SUPABASE: PICKS
# ============================================================

def get_draft_picks(season_id: int) -> list[dict]:
    """Lädt alle Picks in der korrekten Reihenfolge."""
    response = (
        supabase
        .table("draft_picks")
        .select("*")
        .eq("season_id", season_id)
        .order("pick_order")
        .execute()
    )

    return daten_oder_leere_liste(response)


def save_draft_pick(
    season_id: int,
    player_id: int,
    team_id: int,
    pick_order: int,
) -> None:
    """
    Speichert einen Draftpick in draft_picks
    und zusätzlich in player_picks.
    """
    draft_pick = {
        "season_id": season_id,
        "player_id": player_id,
        "team_id": team_id,
        "pick_order": pick_order,
    }

    (
        supabase
        .table("draft_picks")
        .insert(draft_pick)
        .execute()
    )

    player_pick = {
        "season_id": season_id,
        "player_id": player_id,
        "team_id": team_id,
        "pick_order": pick_order,
    }

    (
        supabase
        .table("player_picks")
        .upsert(
            player_pick,
            on_conflict="season_id,player_id,team_id",
        )
        .execute()
    )


def delete_all_draft_picks(season_id: int) -> None:
    """Löscht alle Picks einer Saison."""
    (
        supabase
        .table("draft_picks")
        .delete()
        .eq("season_id", season_id)
        .execute()
    )

    (
        supabase
        .table("player_picks")
        .delete()
        .eq("season_id", season_id)
        .execute()
    )


# ============================================================
# OPENLIGADB
# ============================================================

def get_bundesliga_table(season_year: int) -> list[dict]:
    """
    Lädt die Bundesliga-Tabelle von OpenLigaDB.

    Für die laufende Saison kann es am Anfang der Saison
    noch wenige oder keine Daten geben.
    """
    url = (
        "https://www.openligadb.de/api/"
        f"getbltable/bl1/{season_year}"
    )

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return []


# ============================================================
# AUSWERTUNG
# ============================================================

def berechne_punkte(
    picks: list[dict],
    players: list[dict],
    table_data: list[dict],
) -> tuple[pd.DataFrame, dict]:
    """
    Berechnet die Gesamtpunkte pro Spieler
    und die Punkte der einzelnen Teams.
    """
    punkte_pro_team = {}

    for row in table_data:
        original_name = row.get("teamName", "")
        points = int(row.get("points", 0))
        punkte_pro_team[original_name.lower()] = points

    ergebnisse = {}

    for player in players:
        player_id = player["id"]
        name = player["name"]

        eigene_picks = [
            pick
            for pick in picks
            if pick["player_id"] == player_id
        ]

        einzelteams = []
        gesamtpunkte = 0
        gesamtspiele = 0

        for pick in eigene_picks:
            team = next(
                (
                    team
                    for team in st.session_state.current_teams
                    if team["id"] == pick["team_id"]
                ),
                None,
            )

            if not team:
                continue

            team_display_name = team["team_name"]
            team_points = 0
            team_matches = 0

            # OpenLigaDB-Namen möglichst tolerant vergleichen
            for api_team_name, points in punkte_pro_team.items():
                if (
                    team_display_name.lower() in api_team_name
                    or api_team_name in team_display_name.lower()
                ):
                    team_points = points
                    break

            for row in table_data:
                api_name = row.get("teamName", "").lower()

                if (
                    team_display_name.lower() in api_name
                    or api_name in team_display_name.lower()
                ):
                    team_matches = int(row.get("matches", 0))
                    break

            gesamtpunkte += team_points
            gesamtspiele += team_matches

            einzelteams.append({
                "Team": team_display_name,
                "Punkte": team_points,
                "Spiele": team_matches,
            })

        ergebnisse[name] = {
            "Punkte": gesamtpunkte,
            "Spiele": gesamtspiele,
            "Teams": einzelteams,
        }

    rangliste = pd.DataFrame([
        {
            "Name": name,
            "Punkte": daten["Punkte"],
            "Spiele": daten["Spiele"],
        }
        for name, daten in ergebnisse.items()
    ])

    if not rangliste.empty:
        rangliste = rangliste.sort_values(
            by=["Punkte", "Spiele"],
            ascending=[False, False],
        ).reset_index(drop=True)

        rangliste.insert(
            0,
            "Platz",
            range(1, len(rangliste) + 1),
        )

    return rangliste, ergebnisse


# ============================================================
# DARSTELLUNG
# ============================================================

def zeige_draft_reihenfolge(
    draft_order: list[dict],
    players: list[dict],
    current_pick: int,
) -> None:
    """Zeigt alle 16 Picks inklusive Status."""
    st.subheader("🎲 Draft-Reihenfolge")

    if not draft_order:
        st.info("Die Draft-Reihenfolge wurde noch nicht ausgelost.")
        return

    rows = []

    for row in draft_order:
        position = row["position"]
        name = spieler_name(players, row["player_id"])

        if position < current_pick:
            status = "✅ erledigt"
        elif position == current_pick:
            status = "▶️ aktuell"
        else:
            status = "⏳ offen"

        rows.append({
            "Pick": position,
            "Spieler": name,
            "Status": status,
        })

    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True,
        hide_index=True,
    )


def zeige_finale_picks(
    picks: list[dict],
    players: list[dict],
    teams: list[dict],
) -> None:
    """Zeigt die finalen Teams pro Spieler."""
    st.subheader("🏆 Finale Teamverteilung")

    for player in players:
        eigene_picks = [
            pick
            for pick in picks
            if pick["player_id"] == player["id"]
        ]

        if not eigene_picks:
            continue

        st.markdown(f"### {player['name']}")

        team_rows = []

        for pick in eigene_picks:
            team = next(
                (
                    team
                    for team in teams
                    if team["id"] == pick["team_id"]
                ),
                None,
            )

            if team:
                team_rows.append({
                    "Pick": pick["pick_order"],
                    "Team": team["team_name"],
                    "Logo": team.get("logo_url", ""),
                })

        st.dataframe(
            pd.DataFrame(team_rows),
            use_container_width=True,
            hide_index=True,
        )


def zeige_verfuegbare_teams(teams: list[dict], picks: list[dict]) -> None:
    """Zeigt alle noch verfügbaren Teams."""
    gepickte_team_ids = {
        pick["team_id"]
        for pick in picks
    }

    available_teams = [
        team
        for team in teams
        if team["id"] not in gepickte_team_ids
    ]

    st.subheader(
        f"⚽ Verfügbare Teams ({len(available_teams)})"
    )

    columns = st.columns(6)

    for index, team in enumerate(available_teams):
        with columns[index % 6]:
            logo_url = team.get("logo_url")

            if logo_url and logo_url.startswith("http"):
                st.image(logo_url, width=60)

            st.caption(team["team_name"])


# ============================================================
# APP
# ============================================================

st.title("⚽ Bundesliga Tippspiel")

try:
    season = get_or_create_season(AKTUELLE_SAISON)
except Exception as error:
    st.error(f"Die Saison konnte nicht geladen werden: {error}")
    st.stop()

season_id = season["id"]

players = get_players()
teams = get_teams_for_season(season_id)
draft_status = get_draft_status(season_id)

# Für die Auswertungsfunktion verfügbar machen
st.session_state.current_teams = teams

if len(players) != ANZAHL_SPIELER:
    st.warning(
        f"Es müssen genau {ANZAHL_SPIELER} Spieler vorhanden sein. "
        f"Aktuell gefunden: {len(players)}."
    )

if not players:
    st.error("Keine Spieler in Supabase gefunden.")
    st.stop()

st.sidebar.header("👤 Profil")

player_names = [player["name"] for player in players]

current_player_name = st.sidebar.selectbox(
    "Wer bist Du?",
    player_names,
)

is_admin = current_player_name == ADMIN_USER

if is_admin:
    st.sidebar.success("✅ Adminmodus aktiv")
else:
    st.sidebar.info(f"👀 Angemeldet als {current_player_name}")

st.sidebar.divider()
st.sidebar.write(f"**Saison:** {AKTUELLE_SAISON}")
st.sidebar.write(f"**Draftstatus:** `{draft_status}`")

tab_draft, tab_overview, tab_admin = st.tabs([
    "🎲 Draft",
    "📊 Saisonübersicht",
    "⚙️ Administration",
])


# ============================================================
# TAB: DRAFT
# ============================================================

with tab_draft:
    draft_order = get_draft_order(season_id)
    draft_picks = get_draft_picks(season_id)

    current_pick_number = len(draft_picks) + 1

    if draft_status == "waiting":
        st.subheader("🎲 Auslosung")

        st.info(
            "Zuerst wird ausgelost, wer auf Position 1 bis 4 sitzt. "
            "Danach beginnt der Team-Draft."
        )

        if is_admin:
            if st.button(
                "🎰 Sitzreihenfolge auslosen",
                type="primary",
            ):
                shuffled_players = players.copy()
                random.shuffle(shuffled_players)

                first_round_player_ids = [
                    player["id"]
                    for player in shuffled_players
                ]

                complete_order_ids = [
                    first_round_player_ids[index]
                    for index in SNAKE_REIHENFOLGE
                ]

                save_draft_order(
                    season_id,
                    complete_order_ids,
                )

                update_draft_status(
                    season_id,
                    "drawing",
                )

                st.success(
                    "Die Draft-Reihenfolge wurde erfolgreich ausgelost."
                )
                st.rerun()
        else:
            st.info(
                "Warte, bis der Admin die Sitzreihenfolge auslost."
            )

    elif draft_status == "drawing":
        st.subheader("✅ Auslosung abgeschlossen")

        zeige_draft_reihenfolge(
            draft_order,
            players,
            current_pick_number,
        )

        if is_admin:
            st.warning(
                "Bitte überprüfe die Reihenfolge. "
                "Danach kannst Du den Team-Draft starten."
            )

            if st.button(
                "➡️ Team-Draft starten",
                type="primary",
            ):
                update_draft_status(
                    season_id,
                    "team_draft",
                )
                st.rerun()
        else:
            st.info(
                "Warte, bis der Admin den Team-Draft startet."
            )

    elif draft_status == "team_draft":
        st.subheader("🏆 Team-Draft")

        if not draft_order:
            st.error("Keine Draft-Reihenfolge vorhanden.")
            st.stop()

        zeige_draft_reihenfolge(
            draft_order,
            players,
            current_pick_number,
        )

        if current_pick_number <= ANZAHL_PICKS:
            current_order_row = next(
                (
                    row
                    for row in draft_order
                    if row["position"] == current_pick_number
                ),
                None,
            )

            if not current_order_row:
                st.error("Die aktuelle Draftposition wurde nicht gefunden.")
                st.stop()

            current_player_id = current_order_row["player_id"]
            current_player = spieler_name(
                players,
                current_player_id,
            )

            st.divider()
            st.info(
                f"🎯 **Pick {current_pick_number}: "
                f"{current_player} ist an der Reihe.**"
            )

            zeige_verfuegbare_teams(teams, draft_picks)

            if current_player_name == current_player:
                already_picked_ids = {
                    pick["team_id"]
                    for pick in draft_picks
                }

                available_teams = [
                    team
                    for team in teams
                    if team["id"] not in already_picked_ids
                ]

                if not available_teams:
                    st.error("Keine verfügbaren Teams mehr vorhanden.")
                else:
                    team_options = {
                        team["id"]: team["team_name"]
                        for team in available_teams
                    }

                    selected_team_id = st.selectbox(
                        "Wähle Dein Team:",
                        options=list(team_options.keys()),
                        format_func=lambda team_id: team_options[team_id],
                        key=f"team_select_{current_pick_number}",
                    )

                    if st.button(
                        "✅ Team picken",
                        type="primary",
                    ):
                        try:
                            save_draft_pick(
                                season_id=season_id,
                                player_id=current_player_id,
                                team_id=selected_team_id,
                                pick_order=current_pick_number,
                            )

                            st.success(
                                f"{current_player} hat "
                                f"{team_options[selected_team_id]} gepickt."
                            )

                            if current_pick_number == ANZAHL_PICKS:
                                update_draft_status(
                                    season_id,
                                    "completed",
                                )

                            st.rerun()

                        except Exception as error:
                            st.error(
                                f"Der Pick konnte nicht gespeichert werden: "
                                f"{error}"
                            )
            else:
                st.info(
                    f"Warte auf {current_player}."
                )
        else:
            update_draft_status(
                season_id,
                "completed",
            )
            st.success("🎉 Alle 16 Teams wurden gepickt.")
            st.rerun()

    elif draft_status == "completed":
        st.success("✅ Der Draft ist abgeschlossen.")

        zeige_finale_picks(
            draft_picks,
            players,
            teams,
        )


# ============================================================
# TAB: SAISONÜBERSICHT
# ============================================================

with tab_overview:
    st.subheader(f"📊 Bundesliga-Tabelle {AKTUELLE_SAISON}")

    table_data = get_bundesliga_table(
        AKTUELLES_BUNDESLIGA_JAHR,
    )

    if table_data:
        bundesliga_rows = []

        for index, row in enumerate(
            sorted(
                table_data,
                key=lambda item: item.get("points", 0),
                reverse=True,
            ),
            start=1,
        ):
            bundesliga_rows.append({
                "Platz": index,
                "Team": row.get("teamName", ""),
                "Spiele": row.get("matches", 0),
                "Siege": row.get("won", 0),
                "Unentschieden": row.get("draw", 0),
                "Niederlagen": row.get("lost", 0),
                "Tore": (
                    f"{row.get('goalsFor', 0)}:"
                    f"{row.get('goalsAgainst', 0)}"
                ),
                "Punkte": row.get("points", 0),
            })

        st.dataframe(
            pd.DataFrame(bundesliga_rows),
            use_container_width=True,
            hide_index=True,
        )

        rangliste, einzel_ergebnisse = berechne_punkte(
            draft_picks,
            players,
            table_data,
        )

        st.divider()
        st.subheader("🏆 Rangliste")

        if rangliste.empty:
            st.info(
                "Noch keine Picks oder noch keine Tabellendaten vorhanden."
            )
        else:
            st.dataframe(
                rangliste,
                use_container_width=True,
                hide_index=True,
            )

            st.divider()
            st.subheader("📋 Punkte der Einzelteams")

            for name, result in einzel_ergebnisse.items():
                st.markdown(
                    f"### {name} – {result['Punkte']} Punkte"
                )

                if result["Teams"]:
                    st.dataframe(
                        pd.DataFrame(result["Teams"]),
                        use_container_width=True,
                        hide_index=True,
                    )
                else:
                    st.info("Noch keine Teams vorhanden.")

    else:
        st.warning(
            "Die Bundesliga-Tabelle konnte aktuell nicht geladen werden. "
            "Zu Saisonbeginn kann OpenLigaDB noch keine Spiele enthalten."
        )

    st.divider()
    st.subheader("🏆 Teamverteilung")

    if draft_picks:
        zeige_finale_picks(
            draft_picks,
            players,
            teams,
        )
    else:
        st.info("Es wurden noch keine Teams gepickt.")


# ============================================================
# TAB: ADMINISTRATION
# ============================================================

with tab_admin:
    if not is_admin:
        st.error(
            "Dieser Bereich ist nur für den Admin sichtbar."
        )
    else:
        st.subheader("⚙️ Adminbereich")

        st.write(
            f"**Aktueller Status:** `{draft_status}`"
        )

        st.divider()
        st.markdown("### 🔄 Draft zurücksetzen")

        st.warning(
            "Dabei werden die Auslosung und alle Picks "
            "dieser Saison gelöscht."
        )

        if st.button(
            "🗑️ Draft vollständig zurücksetzen",
            type="secondary",
        ):
            try:
                delete_all_draft_picks(season_id)
                reset_draft_order(season_id)

                st.success(
                    "Der Draft wurde vollständig zurückgesetzt."
                )
                st.rerun()

            except Exception as error:
                st.error(
                    f"Der Draft konnte nicht zurückgesetzt werden: "
                    f"{error}"
                )

        st.divider()
        st.markdown("### ⚠️ Manuellen Status setzen")

        status_options = [
            "waiting",
            "drawing",
            "team_draft",
            "completed",
        ]

        selected_status = st.selectbox(
            "Neuer Status:",
            status_options,
            index=status_options.index(draft_status)
            if draft_status in status_options
            else 0,
        )

        if st.button("Status speichern"):
            update_draft_status(
                season_id,
                selected_status,
            )
            st.success("Status gespeichert.")
            st.rerun()

        st.divider()
        st.markdown("### 👥 Spieler")

        st.dataframe(
            pd.DataFrame(players),
            use_container_width=True,
            hide_index=True,
        )

        st.divider()
        st.markdown("### ⚽ Teams dieser Saison")

        if teams:
            st.dataframe(
                pd.DataFrame(teams),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.warning(
                "Für diese Saison wurden noch keine Teams hinterlegt."
            )
