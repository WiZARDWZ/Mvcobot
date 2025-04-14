import pyodbc
from config import DB_CONFIG
from typing import List, Dict, Optional
from datetime import datetime
import logging

# تنظیمات لاگ‌گیری
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DatabaseConnector:
    def __init__(self):
        self.connection_string = (
            "DRIVER={ODBC Driver 17 for SQL Server};"
            "SERVER=AMIN\\MVCO;"
            "DATABASE=Sepidar01;"
            "Trusted_Connection=yes;"
        )
        self.timeout = 30

    def _get_connection(self):
        try:
            conn = pyodbc.connect(self.connection_string, timeout=self.timeout)
            conn.autocommit = False
            return conn
        except pyodbc.Error as e:
            logger.error(f"خطا در اتصال به دیتابیس: {str(e)}")
            raise

    def fetch_inventory_data(self, part_code: Optional[str] = None) -> List[Dict]:
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    sql_query = """
                    DECLARE @RgParamFiscalYearID INT = (SELECT MAX(FiscalYearId) FROM FMK.FiscalYear);
                    DECLARE @SearchTerm NVARCHAR(100) = ?;

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
                            INV.vwInventoryReceiptItem ri 
                            ON r.InventoryReceiptID = ri.InventoryReceiptRef
                        WHERE 
                            r.FiscalYearRef = @RgParamFiscalYearID 
                            AND r.Type = 1
                    ),
                    Item AS (
                        SELECT 
                            i.UnitTitle,
                            i.Code,
                            i.SaleGroupTitle,
                            p.PropertyAmount1,
                            i.Title,
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
                            AND (@SearchTerm IS NULL OR i.Code LIKE '%' + @SearchTerm + '%')
                    ),
                    StockSumery AS (
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
                    )

                    SELECT 
                        i.Code AS [کد کالا],
                        i.Title AS [نام کالا],
                        i.UnitTitle AS [واحد سنجش],
                        i.SaleGroupTitle AS [گروه فروش],
                        i.PropertyAmount1 AS [مشخصات کالا],
                        p.DelivererCode AS [کد تامین کننده],
                        p.DelivererTitle AS [نام تامین کننده],
                        p.Date AS [تاریخ],
                        p.Number AS [شماره],
                        p.Fee AS [فی خرید],
                        p.Quantity AS [تعداد خرید],
                        p.Price AS [مبلغ خرید],
                        i.StockTitle AS [انبار],
                        COALESCE(p.TracingTitle, s.TracingTitle, 'نا مشخص') AS [عامل ردیابی],
                        s.Quantity AS [موجودی],
                        fs.Fee AS [فی فروش]
                    FROM 
                        Item i
                    LEFT JOIN 
                        purch p 
                        ON i.Code = p.ItemCode 
                        AND i.StockTitle = p.StockTitle
                    LEFT JOIN 
                        StockSumery s 
                        ON i.Code = s.ItemCode 
                        AND i.StockTitle = s.StockTitle 
                        AND COALESCE(p.TracingTitle, '') = COALESCE(s.TracingTitle, '')
                    LEFT JOIN 
                        FeeSale fs 
                        ON i.Code = fs.ItemCode 
                        AND COALESCE(s.TracingTitle, '') = COALESCE(fs.TracingTitle, '')
                    WHERE 
                        s.Quantity IS NOT NULL 
                        AND s.Quantity > 0
                        AND fs.Fee IS NOT NULL
                    ORDER BY
                        i.Code, s.Quantity DESC;
                    """

                    start_time = datetime.now()
                    cursor.execute(sql_query, f"%{part_code}%" if part_code else "")

                    columns = [column[0] for column in cursor.description]
                    results = [dict(zip(columns, row)) for row in cursor.fetchall()]

                    # حذف رکوردهای تکراری
                    unique_results = []
                    seen_codes = set()

                    for item in results:
                        code = item['کد کالا']
                        if code not in seen_codes:
                            seen_codes.add(code)
                            unique_results.append(item)

                    duration = (datetime.now() - start_time).total_seconds()
                    logger.info(f"دریافت {len(unique_results)} رکورد در {duration:.2f} ثانیه")

                    return unique_results

        except pyodbc.Error as e:
            logger.error(f"خطای پایگاه داده: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"خطای ناشناخته: {str(e)}")
            raise

    def check_connection(self) -> bool:
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    return True
        except:
            return False


# نمونه Singleton برای اتصال به دیتابیس
db_connector = DatabaseConnector()


# توابع عمومی برای استفاده در ماژول‌های دیگر
def fetch_inventory_data(part_code: Optional[str] = None) -> List[Dict]:
    return db_connector.fetch_inventory_data(part_code)

def fetch_all_inventory_data() -> List[Dict]:
    """
    دریافت کامل موجودی بدون فیلتر کد خاص، برای کش شدن اولیه
    """
    return db_connector.fetch_inventory_data(part_code=None)

def check_db_connection() -> bool:
    return db_connector.check_connection()
