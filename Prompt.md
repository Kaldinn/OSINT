Jesteś senior Python developerem, security engineerem oraz OSINT engineerem. Masz zaprojektować i stworzyć kompletne, działające narzędzie CLI o nazwie **CustomOSINT**, przeznaczone do Kali Linux / Debian, które automatyzuje legalny OSINT oparty wyłącznie na publicznie dostępnych danych, oficjalnych API oraz narzędziach open-source.

## GŁÓWNY CEL

Chcę móc uruchomić np.:

```bash
python3 CustomOSINT.py investigate --email "example@example.com"
```

lub:

```bash
python3 CustomOSINT.py investigate --nickname "example123"
```

lub:

```bash
python3 CustomOSINT.py investigate \
  --name "Jan Kowalski" \
  --email "jan@example.com" \
  --phone "+48123456789" \
  --nickname "janek93"
```

a narzędzie ma:

1. rozpoznać typy dostarczonych danych,
2. uruchomić odpowiednie moduły OSINT,
3. zebrać wyniki,
4. znormalizować wyniki różnych programów,
5. znaleźć nowe identyfikatory będące potencjalnymi pivotami,
6. opcjonalnie uruchamiać kolejne etapy wyszukiwania na podstawie nowych pivotów,
7. deduplikować wyniki,
8. korelować informacje,
9. obliczać confidence score dla powiązań,
10. zachowywać dowody wskazujące, dlaczego dwie encje zostały powiązane,
11. wygenerować końcowy graf zależności,
12. wygenerować czytelny raport HTML,
13. zachować również wszystkie surowe wyniki narzędzi.

Narzędzie ma być frameworkiem, nie pojedynczym monolitycznym skryptem.

---

# ZASADY BEZPIECZEŃSTWA I LEGALNOŚCI

Projektuj system do:

- własnych audytów,
- testów OSINT,
- CTF,
- szkoleń,
- dochodzeń prowadzonych za zgodą lub w ramach uprawnienia,
- analizy informacji publicznie dostępnych.

Nie implementuj:

- łamania haseł,
- credential stuffing,
- logowania do cudzych kont,
- obchodzenia MFA,
- przejmowania kont,
- phishingu,
- scrapingowania prywatnych danych wymagających zalogowania,
- obchodzenia zabezpieczeń platform,
- kupowania lub automatycznego pobierania baz z wykradzionymi hasłami,
- pobierania danych infostealerów,
- automatycznego wykorzystywania wyciekłych credentiali,
- obchodzenia CAPTCHA,
- abuse password-reset flows,
- automatycznego wysyłania wiadomości, SMS lub requestów mogących powiadomić badaną osobę.

Dane breach exposure mogą być pobierane wyłącznie z legalnych API typu Have I Been Pwned lub podobnych źródeł konfigurowanych przez użytkownika.

---

# ARCHITEKTURA

Repozytorium powinno mieć mniej więcej następującą strukturę:

```text
customosint/
├── CustomOSINT.py
├── requirements.txt
├── pyproject.toml
├── README.md
├── install.sh
├── config.example.yaml
├── .env.example
│
├── customosint/
│   ├── __init__.py
│   ├── cli.py
│   ├── orchestrator.py
│   ├── config.py
│   ├── logging.py
│   ├── database.py
│   │
│   ├── core/
│   │   ├── entities.py
│   │   ├── relationships.py
│   │   ├── evidence.py
│   │   ├── normalizer.py
│   │   ├── correlation.py
│   │   ├── scoring.py
│   │   ├── pivots.py
│   │   ├── deduplication.py
│   │   └── validators.py
│   │
│   ├── providers/
│   │   ├── base.py
│   │   ├── maigret.py
│   │   ├── sherlock.py
│   │   ├── holehe.py
│   │   ├── spiderfoot.py
│   │   ├── ghunt.py
│   │   ├── exiftool.py
│   │   ├── hibp.py
│   │   ├── gravatar.py
│   │   ├── github.py
│   │   ├── keybase.py
│   │   ├── search_engines.py
│   │   └── ...
│   │
│   ├── exporters/
│   │   ├── json.py
│   │   ├── csv.py
│   │   ├── gexf.py
│   │   ├── graphml.py
│   │   ├── neo4j.py
│   │   ├── maltego.py
│   │   └── html.py
│   │
│   └── templates/
│       └── report.html.j2
│
└── tests/
```

Możesz poprawić strukturę, jeśli masz lepszy projekt.

---

# PROVIDER INTERFACE

Każde zewnętrzne narzędzie ma być adapterem implementującym wspólny interfejs.

Przykładowo:

```python
class Provider:
    name: str
    supported_entities: set[str]

    def available(self) -> bool:
        ...

    async def run(self, entity, context):
        ...

    def normalize(self, raw_result):
        ...
```

Provider ma być odpowiedzialny tylko za:

- uruchomienie narzędzia/API,
- odebranie wyniku,
- parsowanie,
- normalizację.

Nie umieszczaj logiki korelacji w providerach.

---

# WSPIERANE ENCJE

Minimum:

```text
Person
FullName
Username
Email
Phone
SocialProfile
URL
Domain
Organization
Location
Image
ImageHash
Breach
IPAddress
GitHubAccount
GoogleAccount
Website
ExternalIdentifier
```

Każda encja powinna posiadać co najmniej:

```json
{
  "id": "...",
  "type": "Username",
  "value": "janek93",
  "normalized_value": "janek93",
  "sources": [],
  "confidence": 0.0,
  "metadata": {},
  "created_at": "...",
  "depth": 1
}
```

---

# RELACJE

Przykładowe relacje:

```text
USES
POSSIBLY_USES
OWNS
POSSIBLY_OWNS
LINKS_TO
HAS_EMAIL
HAS_PHONE
HAS_USERNAME
HAS_PROFILE
HAS_AVATAR
SAME_AVATAR
MENTIONED_IN
APPEARED_IN_BREACH
WORKS_AT
MEMBER_OF
LOCATED_IN
DERIVED_FROM
FOUND_BY
```

Relacja ma mieć:

```json
{
  "source": "...",
  "target": "...",
  "relation": "POSSIBLY_USES",
  "confidence": 0.78,
  "evidence": [],
  "providers": [],
  "created_at": "..."
}
```

---

# NARZĘDZIA DO INTEGRACJI

Spróbuj wykorzystać możliwie szeroki, ale rozsądny zestaw narzędzi.

## Username OSINT

Priorytet:

- Maigret
- Sherlock

Opcjonalnie, jeżeli nadal aktywne i sensowne:

- WhatsMyName
- Blackbird
- socialscan

Preferuj machine-readable output typu JSON / NDJSON / CSV zamiast parsowania kolorowanego stdout.

---

## Email OSINT

Integracja z:

- Holehe
- GHunt
- Gravatar
- GitHub public information
- Keybase
- public GitLab information
- legalnymi providerami reputation/enrichment, jeśli użytkownik poda API key

Z emaila automatycznie wyciągaj local-part jako potencjalny username.

Przykład:

```text
john.smith93@gmail.com
```

generuje między innymi:

```text
john.smith93
johnsmith93
```

ale wygenerowane warianty oznaczaj jako hipotezy o niższym confidence.

---

# BREACH EXPOSURE

Obsłuż:

- Have I Been Pwned API

Klucze API mają znajdować się w:

```text
.env
```

lub:

```yaml
providers:
  hibp:
    enabled: true
    api_key_env: HIBP_API_KEY
```

Nie umieszczaj kluczy w kodzie.

Nie pobieraj ani nie przechowuj plaintext passwordów.

Nie implementuj automatycznego pobierania breach dumpów.

Jeżeli API nie jest skonfigurowane, provider powinien mieć status:

```text
SKIPPED: API key missing
```

a nie powodować błędu całego dochodzenia.

---

# SPIDERFOOT

Zintegruj SpiderFoot jako dodatkowy enrichment engine.

Nie pozwól jednak, aby jego wynik automatycznie został uznany za prawdziwy.

Wyniki SpiderFoot mają przechodzić przez ten sam normalizer, deduplikację i scoring co reszta.

Jeśli SpiderFoot potrafi eksportować machine-readable JSON/CSV/GEXF, wykorzystaj najstabilniejszą metodę.

---

# OBRAZY

Dla:

```bash
--image photo.jpg
```

wykonuj automatycznie:

- ExifTool,
- SHA256,
- MD5 tylko jako identyfikator pliku, nie do bezpieczeństwa,
- perceptual hash,
- pHash,
- dHash,
- podstawowe informacje o wymiarach obrazu.

Zapisuj:

```text
camera
datetime
GPS, jeśli istnieje
software
author
copyright
EXIF
XMP
IPTC
```

Nie zakładaj, że brak EXIF oznacza, że obraz jest fałszywy.

Jeżeli dwa avatary mają podobny perceptual hash, dodaj relację:

```text
POSSIBLE_SAME_IMAGE
```

i odpowiedni score.

Nie próbuj automatycznie obchodzić mechanizmów Google Lens/TinEye.

Możesz natomiast w raporcie wygenerować dla znalezionych obrazów sekcję:

```text
Reverse Image Search
```

z wygodnymi linkami/pivotami do legalnych usług wyszukiwania obrazem, o ile da się to zrobić zgodnie z ich publicznymi mechanizmami.

---

# PHONE

Normalizuj numery do E.164, jeśli to możliwe.

Dla:

```text
+48 123 456 789
123456789
```

stwórz jedną kanoniczną encję.

Nie stosuj contact discovery w WhatsApp/Telegram/Signal ani innych aplikacjach poprzez masowe dodawanie numerów do książki adresowej.

Możesz wykorzystywać wyłącznie publiczne wyniki wyszukiwarek, strony, ogłoszenia, wizytówki i jawne API.

---

# NAME OSINT

Samo imię i nazwisko ma mieć niską wartość identyfikacyjną.

Nie łącz profili tylko dlatego, że mają:

```text
Jan Kowalski
```

Dopiero kombinacja dodatkowych cech może podnieść score.

---

# AUTOMATYCZNE PIVOTOWANIE

To jedna z najważniejszych części.

Implementuj mechanizm kolejki BFS/priority queue.

Przykład:

```text
EMAIL
 ↓
local-part
 ↓
USERNAME
 ↓
Maigret
 ↓
GitHub profile
 ↓
different username
 ↓
NEW USERNAME
 ↓
Maigret + Sherlock
```

Każda encja ma `depth`.

Domyślne:

```text
--depth 2
```

Maksymalne rekomendowane:

```text
--depth 3
```

Dodaj zabezpieczenia:

```text
--max-entities
--max-provider-runs
--timeout
--provider-timeout
```

aby zapobiec eksplozji grafu.

Domyślnie preferuj jako nowe pivoty tylko dane o odpowiednio wysokiej jakości.

Przykładowo:

```text
confidence < 0.40 -> nie pivotuj
```

chyba że użytkownik poda:

```bash
--aggressive
```

---

# CONFIDENCE SCORING

Stwórz dobrze zaprojektowany scoring oparty na evidence.

Nie używaj prostego:

```python
score += 20
```

wszędzie bez kontekstu.

Wydziel osobny scoring engine.

Przykładowe sygnały:

```text
same exact email                very strong
direct profile link             very strong
same rare username              medium/strong
same common username            weak
same avatar perceptual hash     medium/strong
same full name                  weak
same city                       weak
same organization               weak/medium
same unique website             strong
same bio URL                    strong
multiple independent matches    confidence boost
```

Zastosuj diminishing returns, aby 10 słabych sygnałów nie dawało automatycznie 100%.

Klasyfikacja:

```text
0.00–0.29 LOW
0.30–0.59 POSSIBLE
0.60–0.79 PROBABLE
0.80–1.00 STRONG
```

Każdy edge ma zachowywać listę dowodów.

Przykład:

```text
GitHub account ↔ Reddit account

confidence: 0.87

Evidence:
✓ identical rare username
✓ identical avatar perceptual hash
✓ same personal website
✓ matching display name
```

---

# FALSE POSITIVE PROTECTION

To krytyczne.

Nigdy:

```text
same username = same person
```

automatycznie.

Implementuj:

- canonical normalization,
- deduplication,
- common username penalty,
- name frequency penalty, jeśli sensowne,
- independent-source requirement,
- conflicting evidence.

Przykład konfliktu:

```text
GitHub:
location = Warsaw

Instagram:
location = Toronto
```

powinien obniżyć confidence.

---

# DATABASE

Użyj SQLite.

Minimum tabele:

```text
cases
entities
relationships
evidence
provider_runs
raw_results
images
```

Wszystkie wyniki muszą być powtarzalne i możliwe do audytowania.

Provider run zapisuje:

```text
provider
input
started_at
finished_at
status
return_code
raw_output_file
error
```

---

# STRUKTURA CASE

Każde dochodzenie:

```text
cases/
└── 2026-10-13_163000_case-name/
    ├── case.db
    ├── case.json
    ├── seeds.json
    │
    ├── raw/
    │   ├── maigret/
    │   ├── sherlock/
    │   ├── holehe/
    │   ├── spiderfoot/
    │   └── ...
    │
    ├── normalized/
    │   ├── entities.jsonl
    │   ├── relationships.jsonl
    │   └── evidence.jsonl
    │
    ├── images/
    │
    ├── graph/
    │   ├── case.gexf
    │   ├── case.graphml
    │   ├── neo4j.cypher
    │   └── maltego_import.csv
    │
    └── report/
        └── index.html
```

---

# GRAPH

Graf powinien być podstawowym rezultatem dochodzenia.

Węzły powinny mieć różne typy:

```text
Person
Email
Username
Phone
SocialProfile
Image
Website
Domain
Organization
Breach
Location
```

Eksportuj:

### GEXF

do Gephi.

### GraphML

do innych narzędzi.

### Neo4j Cypher

np.:

```text
neo4j.cypher
```

który można zaimportować do Neo4j.

### Maltego

Generuj przygotowany:

```text
maltego_import.csv
```

z kolumnami pozwalającymi mapować:

```text
SourceType
SourceValue
Relation
TargetType
TargetValue
Confidence
Evidence
Provider
```

Nie automatyzuj GUI Maltego.

---

# HTML REPORT

Raport HTML ma być jednym z głównych rezultatów.

Powinien zawierać:

## Executive Summary

```text
Input seeds: 4
Unique entities: 61
Social profiles: 17
Possible additional usernames: 5
Images: 9
Breaches: 3
Strong relationships: 8
Probable relationships: 11
```

## Seeds

## Profiles

Tabela:

```text
Platform
Username
URL
Confidence
Source
Status
```

## Emails

## Phone numbers

## Breach exposure

Bez haseł.

## Images

Miniatury + metadata.

## Relationships

Najważniejsze korelacje wraz z dowodami.

## Uncertain findings

Oddziel wyniki niepewne od potwierdzonych.

## Provider errors

Pokaż, które narzędzie nie zadziałało.

---

# INTERAKTYWNY GRAF HTML

Oprócz GEXF wygeneruj lokalny interaktywny graf w HTML.

Możesz użyć np.:

- pyvis,
- Cytoscape.js,
- vis-network,
- D3.js.

Powinien działać lokalnie.

Kliknięcie w węzeł pokazuje:

```text
type
value
confidence
providers
metadata
evidence
```

Filtrowanie:

```text
minimum confidence
entity type
provider
depth
```

---

# CLI

Użyj Typer lub Click.

Docelowe komendy:

```bash
customosint investigate
customosint providers
customosint report
customosint graph
customosint cases
customosint show
customosint doctor
```

Przykłady:

```bash
customosint investigate \
  --email "example@example.com"
```

```bash
customosint investigate \
  --nickname "example"
```

```bash
customosint investigate \
  --name "Example User" \
  --email "example@example.com" \
  --phone "+48123456789" \
  --nickname "example93" \
  --depth 2
```

```bash
customosint investigate \
  --nickname "example93" \
  --providers maigret,sherlock
```

```bash
customosint providers
```

Output:

```text
PROVIDER       STATUS          INPUT

Maigret        READY           username
Sherlock       READY           username
Holehe         READY           email
SpiderFoot     READY           multiple
GHunt          READY           email
ExifTool       READY           image
HIBP           NO API KEY      email
GitHub         NO API KEY      username/email
```

---

# DOCTOR

Implementuj:

```bash
customosint doctor
```

który sprawdza:

```text
Python version
venv
Maigret
Sherlock
Holehe
SpiderFoot
GHunt
ExifTool
Neo4j optional
API keys
filesystem permissions
network connectivity
```

i daje instrukcję naprawy.

---

# INSTALACJA

Projekt ma działać na świeżym Kali Linux.

Przygotuj:

```bash
sudo ./install.sh
```

ale instalator ma być przejrzysty.

Nie wykonuj ukrytych zmian systemowych.

Preferuj:

```text
python3-venv
pipx
venv
apt
```

zależnie od narzędzia.

Nie instaluj pakietów Pythona globalnie przez `sudo pip`.

Instalator powinien wykrywać już zainstalowane programy.

---

# ASYNC

Tam, gdzie jest to bezpieczne, uruchamiaj niezależne providery współbieżnie:

```python
asyncio
```

ale implementuj:

```text
global concurrency limit
per-provider concurrency
timeouts
retry with exponential backoff
rate limiting
```

Nie bombarduj publicznych usług requestami.

Domyślnie używaj konserwatywnych limitów.

---

# CACHE

Zaimplementuj cache.

Jeżeli:

```text
Maigret(username123)
```

było wykonane 2 minuty temu, nie uruchamiaj ponownie bez potrzeby.

Konfigurowalne TTL.

Opcja:

```bash
--no-cache
```

---

# RAW DATA

Nigdy nie wyrzucaj surowych wyników.

Każde narzędzie zapisuje wynik w:

```text
raw/provider/
```

Normalizator działa dopiero na kopii.

Dzięki temu można później debugować parser.

---

# LOGGING

Dodaj:

```bash
-v
-vv
--debug
```

Normalny terminal nie powinien być zalany tysiącami linii.

Przykład:

```text
[+] Investigation: john-doe

[+] EMAIL
    john@example.com

[+] Holehe
    4 possible services

[+] Derived username
    john

[+] USERNAME
    john

[+] Maigret
    11 possible profiles

[+] Sherlock
    9 possible profiles

[+] Correlation
    14 unique profiles
    6 probable
    3 strong
    5 uncertain

[+] Graph
    cases/.../graph/case.gexf

[+] Report
    cases/.../report/index.html
```

---

# CONFIG

Przykład:

```yaml
general:
  default_depth: 2
  minimum_pivot_confidence: 0.40
  max_entities: 500
  max_provider_runs: 200

providers:
  maigret:
    enabled: true

  sherlock:
    enabled: true

  holehe:
    enabled: true

  spiderfoot:
    enabled: true

  ghunt:
    enabled: true

  hibp:
    enabled: true
    api_key_env: HIBP_API_KEY

graph:
  gexf: true
  graphml: true
  neo4j: true
  maltego: true

report:
  html: true
  interactive_graph: true
```

---

# QUALITY

Kod ma:

- używać type hints,
- mieć docstrings,
- mieć sensowne wyjątki,
- nie używać `shell=True`, jeśli nie jest potrzebne,
- bezpiecznie obsługiwać subprocess,
- walidować input,
- posiadać testy jednostkowe,
- rozdzielać core logic od providerów,
- działać poprawnie, nawet jeśli część providerów nie jest zainstalowana.

Nie zakładaj, że stdout danego narzędzia nigdy się nie zmieni.

Jeżeli program posiada stabilny JSON output, zawsze preferuj JSON.

---

# TESTY

Stwórz testy dla:

- email normalization,
- phone normalization,
- username normalization,
- entity deduplication,
- relation deduplication,
- confidence scoring,
- pivot depth,
- max entities,
- provider failure,
- timeout,
- malformed JSON,
- missing program,
- missing API key,
- graph export.

Do testów providerów stosuj mocked outputs zamiast wykonywania publicznych requestów.

---

# DEVELOPMENT MODE

Dodaj możliwość:

```bash
customosint investigate --fixture tests/fixtures/example_case/
```

dzięki której można przetestować cały pipeline bez wykonywania OSINT-u w Internecie.

---

# WAŻNE: NIE HALUCYNUJ INTEGRACJI

Przed implementacją każdego providera:

1. sprawdź aktualną dokumentację programu,
2. sprawdź aktualne CLI,
3. sprawdź dostępne machine-readable output,
4. sprawdź status projektu,
5. sprawdź ograniczenia API.

Jeżeli konkretne narzędzie jest nieaktualne albo niestabilne:

- nie udawaj, że działa,
- oznacz provider jako experimental albo pomiń go,
- zaproponuj aktualnie utrzymywaną alternatywę.

---

# KOLEJNOŚĆ IMPLEMENTACJI

Nie próbuj implementować wszystkiego naraz.

## Phase 1

Zbuduj:

- CLI,
- SQLite,
- Entity,
- Relationship,
- Evidence,
- Provider interface,
- normalizer,
- deduplication,
- scoring,
- pivot queue.

## Phase 2

Dodaj:

- Maigret,
- Sherlock,
- Holehe.

Uruchom pełny test pipeline.

## Phase 3

Dodaj:

- SpiderFoot,
- GHunt,
- ExifTool.

## Phase 4

Dodaj:

- HIBP,
- Gravatar,
- GitHub,
- Keybase,
- inne sensowne publiczne API.

## Phase 5

Dodaj:

- GEXF,
- GraphML,
- Neo4j,
- Maltego CSV,
- interaktywny graf HTML.

## Phase 6

Dodaj:

- raport HTML,
- cache,
- async,
- rate limiting,
- installation doctor.

---

# OUTPUT, KTÓREGO OD CIEBIE OCZEKUJĘ

Nie dawaj mi tylko przykładowego kodu lub pseudokodu.

Masz stworzyć działające repozytorium.

Pracuj iteracyjnie.

Najpierw:

1. pokaż finalną architekturę,
2. sprawdź aktualność narzędzi i ich interfejsów,
3. utwórz strukturę repo,
4. zaimplementuj core,
5. dodaj pierwszych providerów,
6. napisz testy,
7. uruchom testy,
8. napraw błędy,
9. uruchom przykładowy fixture case,
10. pokaż końcowy wynik.

Jeżeli masz możliwość wykonywania poleceń w systemie, faktycznie uruchamiaj:

```bash
pytest
ruff
mypy
```

i poprawiaj problemy.

Nie kończ pracy po wygenerowaniu pojedynczych plików.

---

# README

README ma zawierać:

- czym jest CustomOSINT,
- diagram architektury,
- instalację Kali Linux,
- przykłady CLI,
- opis providerów,
- konfigurację API keys,
- opis grafów,
- scoring,
- interpretację confidence,
- troubleshooting,
- zasady legalnego użycia.

---

# FINALNY CEL UX

Chcę finalnie wykonać:

```bash
customosint investigate \
  --email "example@example.com" \
  --nickname "example93" \
  --depth 2
```

i dostać:

```text
Investigation complete.

Seeds:                 2
Entities:             83
Relationships:       116
Social profiles:      19
Additional usernames:  4
Images:                7
Breach exposures:      2

Strong relations:      8
Probable relations:   14
Possible relations:   22

Report:
cases/example/report/index.html

Interactive graph:
cases/example/graph/index.html

Gephi:
cases/example/graph/case.gexf

Maltego:
cases/example/graph/maltego_import.csv

Neo4j:
cases/example/graph/neo4j.cypher
```

Najważniejszym elementem projektu jest:

**seed → enrichment → normalization → correlation → evidence → controlled pivoting → graph → report**

a nie samo uruchomienie jak największej liczby narzędzi.

Jeżeli dwie rzeczy mogą należeć do tej samej osoby, ale nie ma wystarczających dowodów, pokaż je jako potencjalne powiązanie z niskim confidence, zamiast przedstawiać jako fakt.

Buduj projekt tak, żeby późniejsze dodanie kolejnego providera wymagało stworzenia jednego adaptera, a nie modyfikowania całej aplikacji.