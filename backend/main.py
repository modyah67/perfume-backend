from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import sqlite3
import os
import shutil
import webbrowser
import urllib.parse

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Folders
os.makedirs("uploads/products", exist_ok=True)
os.makedirs("uploads/payments", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# DB Helper
def get_db():
    conn = sqlite3.connect("shop.db")
    conn.row_factory = sqlite3.Row
    return conn

# Init DB - آمن للتحديثات (يضيف الأعمدة لو مش موجودة)
with get_db() as conn:
    cur = conn.cursor()

    # جدول المنتجات
    cur.execute("""
    CREATE TABLE IF NOT EXISTS products(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        price TEXT,
        description TEXT,
        image TEXT
    )
    """)

    # جدول الطلبات
    cur.execute("""
    CREATE TABLE IF NOT EXISTS orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product TEXT,
        price TEXT,
        name TEXT,
        phone TEXT,
        payment_image TEXT,
        payment_method TEXT,
        status TEXT
    )
    """)

    # إضافة العمود payment_method لو الجدول قديم ومش موجود فيه
    try:
        cur.execute("ALTER TABLE orders ADD COLUMN payment_method TEXT")
    except sqlite3.OperationalError:
        pass  # العمود موجود بالفعل

    # إضافة العمود status لو مش موجود (احتياطي)
    try:
        cur.execute("ALTER TABLE orders ADD COLUMN status TEXT")
    except sqlite3.OperationalError:
        pass  # العمود موجود بالفعل

    conn.commit()

# Products Routes
@app.post("/add-product")
def add_product(
    name: str = Form(...),
    price: str = Form(...),
    description: str = Form(...),
    image: UploadFile = File(...)
):
    conn = get_db()
    cur = conn.cursor()

    filename = f"products/{image.filename}"
    path = f"uploads/{filename}"

    with open(path, "wb") as f:
        shutil.copyfileobj(image.file, f)

    cur.execute(
        "INSERT INTO products(name,price,description,image) VALUES (?,?,?,?)",
        (name, price, description, filename)
    )
    conn.commit()
    conn.close()

    return {"message": "تم رفع المنتج بنجاح"}

@app.get("/products")
def get_products():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM products")
    rows = cur.fetchall()
    conn.close()

    return [dict(r) for r in rows]

@app.delete("/delete-product/{pid}")
def delete_product(pid: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM products WHERE id=?", (pid,))
    conn.commit()
    conn.close()
    return {"message": "تم حذف المنتج"}

# Orders Routes - محدث للطرق اليدوية (COD, VodafoneCash, InstaPay)
@app.post("/order")
def make_order(
    product: str = Form(...),
    price: str = Form(...),
    name: str = Form(...),
    phone: str = Form(...),
    payment_method: str = Form(...),  # COD, VodafoneCash, InstaPay
    payment_image: UploadFile = File(None)  # مطلوب فقط لو مش COD
):
    conn = get_db()
    cur = conn.cursor()

    filename = None
    if payment_method != "COD" and payment_image:
        filename = f"payments/{payment_image.filename}"
        path = f"uploads/{filename}"
        with open(path, "wb") as f:
            shutil.copyfileobj(payment_image.file, f)

    cur.execute("""
        INSERT INTO orders(product, price, name, phone, payment_image, payment_method, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (product, price, name, phone, filename, payment_method, "قيد المراجعة"))

    conn.commit()
    conn.close()

    return {"message": "تم إرسال الطلب بنجاح"}

@app.get("/orders")
def get_orders():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM orders")
    rows = cur.fetchall()
    conn.close()

    return [dict(r) for r in rows]

@app.put("/confirm-order/{oid}")
def confirm_order(oid: int):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("UPDATE orders SET status='تم التأكيد' WHERE id=?", (oid,))
    cur.execute("SELECT name, phone, product FROM orders WHERE id=?", (oid,))
    row = cur.fetchone()

    conn.commit()
    conn.close()

    if row:
        msg = f"مرحباً {row['name']}، تم تأكيد طلبك لـ ({row['product']}) بنجاح ✅\nنشكرك على ثقتك فينا ❤️"
        url = f"https://wa.me/2{row['phone']}?text={urllib.parse.quote(msg)}"
        webbrowser.open(url)

    return {"message": "تم تأكيد الطلب ورسالة واتساب تم إرسالها للعميل"}

@app.delete("/delete-order/{oid}")
def delete_order(oid: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM orders WHERE id=?", (oid,))
    conn.commit()
    conn.close()
    return {"message": "تم حذف الطلب"}