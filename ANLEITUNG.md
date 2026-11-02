# Streckenatlas – Einrichtung

## 1. Sofort ausprobieren (Demo)
`index.html` im Browser öffnen. Ohne Datenbank läuft die App im Demo-Modus: Alles funktioniert, die Daten bleiben aber nur auf diesem Gerät. Über das Namensfeld oben rechts kannst du zwischen Demo-Admin und zwei Mitarbeitern wechseln und die Löschrechte testen.

## 2. Für das Team: Datenbank anlegen (kostenlos, ca. 10 Minuten)
1. Auf https://supabase.com ein Konto und ein neues Projekt anlegen (Region: Frankfurt).
2. Links **SQL Editor** öffnen, den Inhalt von `supabase-setup.sql` einfügen, **Run**.
3. **Project Settings → API**: `Project URL` und `anon public` Key kopieren.
4. In `index.html` ganz oben im Skript eintragen:
   ```js
   const CONFIG = {
     SUPABASE_URL: "https://xxxx.supabase.co",
     SUPABASE_ANON_KEY: "eyJ..."
   };
   ```
   (Der anon-Key darf öffentlich sein, die Rechte regeln die Zugriffsregeln in der Datenbank.)

## 3. Online stellen
Am einfachsten: https://app.netlify.com/drop öffnen und den Ordner mit `index.html` hineinziehen. Du bekommst eine Adresse, die auf jedem Handy funktioniert. Auf dem Handy über „Zum Startbildschirm hinzufügen“ wie eine App ablegen.

Den Link unter **Supabase → Authentication → URL Configuration** als *Site URL* eintragen.

## 4. Dich selbst zum Admin machen
1. In der App registrieren.
2. Im SQL Editor ausführen: `update public.profiles set role = 'admin' where email = 'deine@mail.de';`
3. Danach schaltest du Kollegen direkt in der App frei (Name oben rechts → Team & Rollen).

## Rechte
| | Wartend | Mitarbeiter | Admin |
|---|---|---|---|
| Karte & Objekte sehen | – | ✓ | ✓ |
| Objekte hinzufügen | – | ✓ | ✓ |
| Eigene Objekte entfernen | – | ✓ | ✓ |
| Fremde Objekte entfernen | – | – | ✓ |
| Kollegen freischalten / Rollen ändern | – | – | ✓ |

## Gut zu wissen
- **Strecken einzeln**: In der Ebenen-Ansicht auf einen Bereich zoomen und „Strecken im Ausschnitt laden“. Die Strecken kommen mit VzG-Nummer aus OpenStreetMap und lassen sich einzeln an- und ausschalten.
- **Datenquellen**: Satellit von Esri, Bahn-Ebenen von OpenRailwayMap. Beide sind frei nutzbar, aber für große Nutzerzahlen nicht gedacht.
- **Sicherheit**: Standorte von Stellwerken gelten als kritische Infrastruktur. Kläre vor dem Einsatz im Team mit deiner Führungskraft bzw. der IT-Sicherheit, ob eine private Lösung wie diese erlaubt ist.
