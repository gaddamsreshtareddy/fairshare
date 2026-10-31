"""Creates one clean demo group with members and varied expenses.

Run from the project folder:  python seed_demo.py
Safe to run twice: it does nothing if the demo group already exists.
"""

from data.database import get_connection, init_db
from services import expense_service as es
from services import group_service as gs
from services import settlement_service as ss

DEMO_NAME = "Goa Trip (Demo)"

init_db()
conn = get_connection()

if any(g.name == DEMO_NAME for g in gs.list_groups(conn)):
    print("Demo group already exists. Nothing to do.")
    raise SystemExit

group = gs.create_group(conn, DEMO_NAME, "INR")
ids = {n: gs.add_member(conn, group.id, n).id for n in ["Sreshta", "Anita", "Rahul", "Kiran"]}
S, A, R, K = ids["Sreshta"], ids["Anita"], ids["Rahul"], ids["Kiran"]
everyone = [S, A, R, K]

# 1. Equal split, one payer
es.add_expense(conn, group.id, "Welcome Dinner", "Food", "2026-10-20",
               payers={S: 120000}, split_method="equal",
               total=120000, member_ids=everyone)

# 2. Custom split: shares in paise
es.add_expense(conn, group.id, "Airport Taxi", "Transport", "2026-10-20",
               payers={R: 60000}, split_method="custom", total=60000,
               shares={S: 15000, A: 15000, R: 30000})

# 3. Percentage split with TWO payers
es.add_expense(conn, group.id, "Beach Hotel", "Hotel", "2026-10-21",
               payers={A: 500000, K: 300000}, split_method="percentage",
               total=800000,
               percentages={S: "40", A: "20", R: "20", K: "20"})

# 4. Item-based split (total = sum of items)
es.add_expense(conn, group.id, "Beach Party", "Food", "2026-10-22",
               payers={K: 120000}, split_method="item",
               items=[("Pizza", 60000, [S, A]),
                      ("Drinks", 30000, [A, R]),
                      ("Dessert", 30000, [S])])

# 5. Foreign currency: $40 at 83.25 INR per USD
es.add_expense(conn, group.id, "Museum Tickets", "Entertainment", "2026-10-23",
               payers={S: 4000}, split_method="equal", total=4000,
               member_ids=everyone, currency="USD", rate="83.25")

ss.generate_plan(conn, group.id)

print(f"Created '{DEMO_NAME}' with 4 members and 5 expenses.")
for member_id, b in es.get_balances(conn, group.id).items():
    print(member_id, b)
conn.close()