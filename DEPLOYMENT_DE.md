# Moodle-Fragenbank auf einem Server betreiben

Anleitung für den Betrieb auf einem kleinen Linux-Server (z. B. im Hochschulnetz),
damit mehrere Personen die Anwendung im Browser nutzen können.

**Voraussetzungen**

- Linux-Server mit **Docker** und **Docker Compose** (`docker compose version` muss funktionieren)
- ca. 2 GB RAM, einige GB freier Speicher
- Netzwerkzugriff auf den gewählten Port (Standard: 8081) für die Nutzer:innen
- Zugriff auf dieses Repository (`git clone …`)

## 1. Installation

```bash
git clone <Repository-URL> moodle-fragenbank
cd moodle-fragenbank
cp .env.prod.example .env
```

In `.env` setzen:

```bash
# Schlüssel erzeugen und bei SECRET_KEY eintragen:
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
# DB_PASSWORD: ein langes, zufälliges Passwort
# HTTP_PORT: Port, unter dem die Seite erreichbar sein soll (Standard 8081)
```

Starten:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Beim ersten Start werden die Datenbank und alle Migrationen automatisch angelegt.
Die Anwendung ist danach erreichbar unter `http://<Server>:8081`.

Der Start verweigert sich absichtlich, wenn `SECRET_KEY` fehlt oder kürzer als
32 Zeichen ist.

## 2. Konten anlegen und Registrierung schließen

1. Mit `REGISTRATION_OPEN=true` (Standard) die gewünschten Konten über die Seite anlegen
   (Registrierung auf der Anmeldeseite).
2. Danach in `.env` `REGISTRATION_OPEN=false` setzen und neu starten:

```bash
docker compose -f docker-compose.prod.yml up -d
```

Ab dann kann sich niemand mehr selbst registrieren.

## 3. HTTPS

Die Anmeldung überträgt ein Passwort. Außerhalb eines vertrauenswürdigen Netzes
sollte die Seite nur über **HTTPS** erreichbar sein. Am einfachsten geht das mit
einem vorgeschalteten Reverse-Proxy (z. B. Caddy, nginx oder der Proxy der
Hochschule), der auf `http://localhost:8081` weiterleitet. Bei `HTTP_PORT`
kann man zusätzlich `127.0.0.1:8081` verwenden, damit der Port nur lokal offen ist.

## 4. Betrieb

| Aufgabe | Befehl |
|---|---|
| Status | `docker compose -f docker-compose.prod.yml ps` |
| Logs | `docker compose -f docker-compose.prod.yml logs -f backend` |
| Stoppen | `docker compose -f docker-compose.prod.yml down` (Daten bleiben erhalten) |
| Update | `git pull && docker compose -f docker-compose.prod.yml up -d --build` |
| Datenbank sichern | `docker compose -f docker-compose.prod.yml exec db pg_dump -U moodle moodleqg > backup.sql` |

Achtung: `down -v` löscht auch die Datenbank. Nicht verwenden, wenn die Daten bleiben sollen.

## 5. Wichtige Hinweise

- Importgrenzen: höchstens 20 Dateien je Import, 10 MB je Datei, 100 MB je Vorgang.
- Die Anwendung ist eigenständig. Sie verbindet sich **nicht** mit Moodle. Fragen kommen
  per XML-Export aus Moodle hinein und gehen per XML-Datei zurück.
- Die Konten sind voneinander getrennt: Fragen eines Kontos sieht kein anderes Konto.
- Der optionale KI-Generator läuft standardmäßig im Offline-Modus (`AI_PROVIDER=mock`).
  Echte Prüfungsfragen nur an einen externen KI-Anbieter senden, wenn das erlaubt ist.
- Die Fragensammlungen können urheberrechtlich geschützt sein. Den Server deshalb
  nur für berechtigte Personen erreichbar machen.
