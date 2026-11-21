# Southern Snacks — Order-to-Audit Management System

A runnable internship prototype for the NIT Tiruchirappalli Order-to-Audit challenge. It connects field orders, admin verification, GST invoices, dispatch, production/BOM consumption, stock ledger, payments, costing and audit exports.

## Run locally

**Requirements:** Python 3.10+.

```bash
# Windows PowerShell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000. The SQLite database and benchmark seed data are created automatically on first run. To reset, stop the server and delete `instance/order_audit.db` (or the SQLite file shown by Flask), then start again. You can also run `flask --app app seed` to seed a fresh database; seed is intentionally non-destructive when users already exist.

**Docker:** `docker compose up --build` then open http://localhost:5000.

## Demo logins

| Role | Username | Password |
|---|---|---|
| Factory admin | `admin` | `admin123` |
| Salesman A | `salesa` | `sales123` |
| Salesman B | `salesb` | `sales123` |
| Production supervisor | `production` | `prod123` |
| External auditor (read-only intent) | `auditor` | `audit123` |
| Owner | `owner` | `owner123` |

Change passwords and `SECRET_KEY` before any public deployment. This is a demo system; do not expose it with the demo credentials.

## Benchmark walkthrough (fresh database)

1. Sign in as `admin`; open **Purchases** and record Flour, quantity `60`, rate `45` (supplier defaults to Local Flour Traders).
2. Open **Production**. Use one batch, expected `200`, good output `188`, wastage `0`, damaged pouches `6`, cartons `9`, labour `1200`, gas/power `600`. Enter actual consumption for oil as `10.5`; leave flour and spice blank (BOM defaults 40 and 1.2). Packaging is automatically set to 194 pouches (188 good + 6 damaged) and 9 cartons. Post run.
3. Sign in as `salesa`; place Retailer A order for 150 Murukku packets.
4. As `admin`, approve, create invoice, then dispatch. Invoice is ₹7,500 taxable + ₹187.50 CGST + ₹187.50 SGST = ₹7,875.
5. Sign in as `salesb`; place Distributor B order for 120. As admin, approve attempt shows stock shortage (32 packets after Retailer A dispatch).
6. Open invoice # for Retailer A and record payment ₹4,000. Outstanding becomes ₹3,875.
7. Open Reports and export Sales, Stock and Production Excel files.

### Benchmark outcomes

- Flour: 100 + 60 − 40 = **120 kg**.
- Oil: 30 − 10.5 = **19.5 L**.
- Pouches: 500 − 188 − 6 = **306 pieces**.
- Cartons: 30 − 9 = **21 pieces**.
- Finished goods: 50 + 188 = **238**, then 238 − 150 = **88 packets**.
- Yield variance: (188 − 200) / 200 = **−6%**, flagged in production detail.
- Oil variance: (10.5 − 10) / 10 = **+5%**; shown in planned-vs-actual run usage.
- Retailer A: **₹7,875 invoice**, **₹3,875 due** after ₹4,000 payment.
- Distributor B: **32 packet shortage**.

## Costing and assumptions

- **Inventory valuation:** moving weighted-average rate, stored in paise per base unit. On receipt, average cost is recalculated from existing quantity/value and the new receipt. This keeps money arithmetic integer-paise based.
- **Run cost:** actual raw/packaging quantities multiplied by current weighted-average rates, plus labour and gas/power entered for that run. Cost per good packet = total run cost / actual good output (rounded down to paise for storage). With benchmark quantities, estimated cost is about **₹31.14 per packet**: flour 40 kg at blended ₹43.125/kg, oil 10.5 L at ₹140/L, spice 1.2 kg at ₹200/kg, 194 pouches at ₹2.50, 9 cartons at ₹15, plus ₹1,800 overhead.
- Pouch usage is 188 saleable packets + 6 damaged pouches. The 9 cartons are entered as actual consumption against the BOM's standard 10.
- GST is 5% for the exercise. Tamil Nadu customers get CGST + SGST; other states get IGST. GSTIN and HSN are sample values only. This is not a certified GST filing or e-invoice application.
- Invoice numbering is a simple sequential demo series (`FY<calendar-year>-NNNN`), not a complete financial-year rollover implementation.
- The benchmark's Distributor B order is submitted after dispatch; the admin stock check prevents approval when only 88 packets remain.

## Features against the brief

**Must-have implemented:** role-based login; product/customer/material/BOM seed masters; mobile-responsive salesman order entry; admin approval with stock check; GST invoice PDF; production run with stock effects; planned-vs-actual usage and yield; stock summary/ledger with source document references; sales/stock Excel exports.

**Should-have implemented:** supplier and purchase receipt; payments and invoice outstanding; run-level material + overhead costing; GST outward summary; variance alert; owner dashboard.

**Stretch implemented:** low-stock/reorder warning; PWA-like responsive browser experience (offline sync is not implemented); audit event log; downloadable Excel reports.

## Architecture / schema

Flask + SQLAlchemy + SQLite. Each posted purchase, production run and dispatch writes a `Movement` row with source type and source ID. Material on-hand and finished stock are updated in the same database transaction as the movement. `ProductionRun` and `RunUsage` preserve expected and actual consumption. `AuditLog` records actor, timestamp, action and entity. Money is represented as integer paise; stock quantities are integer thousandths of the unit shown.

See [DESIGN.md](DESIGN.md) for the data model and calculations.

## Known limitations

- Single factory and one demo product; master editing screens are read-only views. Additions/changes can be made through seed data or database administration.
- No true offline queue/sync, partial dispatch, returns, credit notes, e-way bill, Tally export, multi-warehouse, batch/expiry, or external messaging integration.
- Read-only auditor role can view reports and invoices, but a production-grade deployment should enforce read-only permissions at every route and add more comprehensive tests.
- PDF is a simple prototype tax invoice; verify all legal invoice fields and current GST rules before real use.
- SQLite is suitable for local demonstration. Use PostgreSQL and managed secrets for production deployment.

## Stack choice

A Flask web application was chosen because it is quick to run on a laptop and works on mobile browsers without requiring a separate app installation. SQLAlchemy provides a clear relational schema and transaction boundaries, while SQLite makes the submission reproducible with one command. The stack can move to PostgreSQL for hosted deployment without changing the business model.
