import pyodbc

# Database connection configuration
DB_CONFIG = {
    "driver": "{ODBC Driver 17 for SQL Server}",
    "server": "WIN-9R9B3VCBI6G\\SEPIDAR",
    "database": "Sepidar01",
    "user": "damavand",
    "password": "damavand",
}

# SQL query to fetch inventory and pricing data, including iranCode and deduplicated by highest stock quantity
SQL_QUERY = """
DECLARE @RgParamFiscalYearID INT = (SELECT MAX(FiscalYearId) FROM FMK.FiscalYear);

WITH purch AS (
    SELECT 
        r.Number,
        r.Date,
        r.DelivererCode,
        r.DelivererTitle,
        ri.ItemCode,
        ri.ItemTitle,
        ri.Quantity,
        ri.Fee,
        ri.Price,
        r.StockTitle,
        ri.TracingTitle
    FROM 
        inv.vwInventoryReceipt r 
    LEFT JOIN 
        inv.vwInventoryReceiptItem ri 
        ON r.InventoryReceiptID = ri.InventoryReceiptRef
    WHERE 
        r.FiscalYearRef = @RgParamFiscalYearID 
        AND r.Type = 1
),
Item AS (
    SELECT 
        i.Code,
        i.iranCode             AS [Iran Code],
        i.Title                AS [نام کالا],
        i.UnitTitle            AS [واحد سنجش],
        i.SaleGroupTitle       AS [گروه فروش],
        p.PropertyAmount1      AS [مشخصات کالا],
        ii.StockTitle
    FROM 
        inv.vwItem i
    LEFT JOIN 
        inv.vwItemPropertyAmount p 
        ON i.ItemID = p.ItemRef
    LEFT JOIN 
        inv.vwItemStock ii 
        ON i.ItemID = ii.ItemRef
    WHERE 
        i.Type = 1
),
StockSum AS (
    SELECT 
        ItemCode, 
        StockTitle, 
        SUM(Quantity) AS Quantity, 
        TracingTitle
    FROM 
        inv.vwItemStockSummary
    WHERE 
        FiscalYearRef = @RgParamFiscalYearID
    GROUP BY 
        ItemCode, 
        StockTitle, 
        TracingTitle
),
FeeSale AS (
    SELECT 
        ItemCode, 
        TracingTitle, 
        Fee
    FROM 
        sls.vwPriceNoteItem
    WHERE 
        Fee > 0
),
Joined AS (
    SELECT 
        i.Code             AS [کد کالا],
        i.[Iran Code],
        i.[نام کالا],
        i.[واحد سنجش],
        i.[گروه فروش],
        i.[مشخصات کالا],
        p.DelivererCode    AS [کد تامین کننده],
        p.DelivererTitle   AS [نام تامین کننده],
        p.Date             AS [تاریخ],
        p.Number           AS [شماره],
        p.Fee              AS [فی خرید],
        s.Quantity         AS [موجودی],
        COALESCE(p.TracingTitle, s.TracingTitle, 'نا مشخص') AS [عامل ردیابی],
        fs.Fee             AS [فی فروش]
    FROM 
        Item i
    LEFT JOIN 
        purch p 
        ON i.Code = p.ItemCode 
        AND i.StockTitle = p.StockTitle
    LEFT JOIN 
        StockSum s 
        ON i.Code = s.ItemCode 
        AND i.StockTitle = s.StockTitle 
        AND COALESCE(p.TracingTitle, '') = COALESCE(s.TracingTitle, '')
    LEFT JOIN 
        FeeSale fs 
        ON i.Code = fs.ItemCode 
        AND COALESCE(s.TracingTitle, '') = COALESCE(fs.TracingTitle, '')
    WHERE 
        s.Quantity > 0
        AND fs.Fee IS NOT NULL
),
Ranked AS (
    SELECT 
        *, 
        ROW_NUMBER() OVER (PARTITION BY [کد کالا] ORDER BY [موجودی] DESC) AS rn
    FROM 
        Joined
)
SELECT
    [کد کالا],
    [Iran Code],
    [نام کالا],
    [واحد سنجش],
    [گروه فروش],
    [مشخصات کالا],
    [کد تامین کننده],
    [نام تامین کننده],
    [تاریخ],
    [شماره],
    [فی خرید],
    [موجودی],
    [عامل ردیابی],
    [فی فروش]
FROM 
    Ranked
WHERE 
    rn = 1;
"""

def get_sql_data():
    """
    Connect to SQL Server using DB_CONFIG, execute the query,
    and return a list of dict rows.
    """
    cfg = DB_CONFIG
    connection_string = (
        f"DRIVER={cfg['driver']};"
        f"SERVER={cfg['server']};"
        f"DATABASE={cfg['database']};"
        f"UID={cfg['user']};"
        f"PWD={cfg['password']};"
        "Encrypt=yes;TrustServerCertificate=yes;"
    )

    try:
        conn = pyodbc.connect(connection_string)
        cursor = conn.cursor()
        cursor.execute(SQL_QUERY)
        # Print banner
        print("🤖 Developed By Mohammad Baghshomali | Website : mbaghshomali.ir")
        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()
        data = [dict(zip(columns, row)) for row in rows]
        cursor.close()
        conn.close()
        return data

    except Exception as e:
        print(f"خطا در اتصال به SQL Server: {e}")
        return []
