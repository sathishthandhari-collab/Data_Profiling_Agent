import random
import pandas as pd
from faker import Faker
from typing import List, Dict, Any
import numpy as np
from datetime import datetime, timedelta
from scripts.data_gen.schema_config import ID_PATTERNS, PRODUCT_TYPES, MESSINESS

class BankingDataGenerator:
    def __init__(self, seed: int = 42):
        self.fake = Faker()
        Faker.seed(seed)
        random.seed(seed)
        self.data = {}

    def _inject_messiness(self, df: pd.DataFrame, table_name: str):
        """Injects nulls and outliers based on config."""
        # Inject Nulls
        for col, pct in MESSINESS["null_pct"].items():
            if col in df.columns:
                mask = np.random.rand(len(df)) < pct
                df.loc[mask, col] = None

        # Inject Outliers (for numeric columns)
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            if "id" not in col.lower():  # Don't mess with IDs
                mask = np.random.rand(len(df)) < MESSINESS["outlier_pct"]
                df.loc[mask, col] *= MESSINESS["outlier_multiplier"]
        
        return df

    def generate_all(self, counts: Dict[str, int]):
        """Generates all 8 tables in relational order."""
        
        # 1. Branch
        branches = []
        for i in range(counts.get("branch", 10)):
            branches.append({
                "branch_id": ID_PATTERNS["branch"].format(i+1),
                "branch_name": f"{self.fake.city()} Branch",
                "region": self.fake.state(),
                "swift_code": self.fake.swift()
            })
        self.data["branch"] = pd.DataFrame(branches)

        # 2. Product
        products = []
        for i, p_type in enumerate(PRODUCT_TYPES):
            products.append({
                "product_id": ID_PATTERNS["product"].format(i+1),
                "product_name": f"{p_type} Classic",
                "product_type": p_type,
                "base_rate": round(random.uniform(0.01, 0.08), 4)
            })
        self.data["product"] = pd.DataFrame(products)

        # 3. Customer
        customers = []
        for i in range(counts.get("customer", 1000)):
            customers.append({
                "customer_id": ID_PATTERNS["customer"].format(i+1),
                "full_name": self.fake.name(),
                "customer_type": random.choice(["CORPORATE", "INSTITUTIONAL", "SME"]),
                "country": self.fake.country(),
                "tax_id": self.fake.ssn(),
                "email": self.fake.company_email()
            })
        self.data["customer"] = pd.DataFrame(customers)

        # 4. Account (Facilities)
        accounts = []
        cust_ids = self.data["customer"]["customer_id"].tolist()
        prod_ids = self.data["product"]["product_id"].tolist()
        br_ids = self.data["branch"]["branch_id"].tolist()
        
        for i in range(counts.get("account", 5000)):
            accounts.append({
                "account_id": ID_PATTERNS["account"].format(i+1),
                "customer_id": random.choice(cust_ids),
                "product_id": random.choice(prod_ids),
                "branch_id": random.choice(br_ids),
                "currency": random.choice(["USD", "EUR", "GBP", "JPY"]),
                "credit_limit": round(random.uniform(100000, 50000000), 2),
                "start_date": self.fake.date_between(start_date="-5y", end_date="today")
            })
        self.data["account"] = pd.DataFrame(accounts)

        # 5. Loan (Drawdowns)
        loans = []
        acc_ids = self.data["account"]["account_id"].tolist()
        for i in range(counts.get("loan", 3000)):
            loans.append({
                "loan_id": ID_PATTERNS["loan"].format(i+1),
                "account_id": random.choice(acc_ids),
                "principal_amount": round(random.uniform(50000, 10000000), 2),
                "interest_rate": round(random.uniform(0.02, 0.12), 4),
                "maturity_date": self.fake.date_between(start_date="today", end_date="+10y"),
                "status": random.choice(["ACTIVE", "PAID_OFF", "DEFAULTED", "DELINQUENT"])
            })
        self.data["loan"] = pd.DataFrame(loans)

        # 6. Collateral
        collaterals = []
        loan_ids = self.data["loan"]["loan_id"].tolist()
        for i in range(counts.get("collateral", 2000)):
            collaterals.append({
                "collateral_id": ID_PATTERNS["collateral"].format(i+1),
                "loan_id": random.choice(loan_ids),
                "collateral_type": random.choice(["REAL_ESTATE", "EQUIPMENT", "CASH", "SECURITIES"]),
                "estimated_value": round(random.uniform(100000, 15000000), 2),
                "valuation_date": self.fake.date_between(start_date="-1y", end_date="today")
            })
        self.data["collateral"] = pd.DataFrame(collaterals)

        # 7. Cashflow (Transactions)
        cashflows = []
        for i in range(counts.get("cashflow", 20000)):
            cashflows.append({
                "cashflow_id": ID_PATTERNS["cashflow"].format(i+1),
                "loan_id": random.choice(loan_ids),
                "amount": round(random.uniform(-500000, 1000000), 2),
                "cashflow_date": self.fake.date_between(start_date="-2y", end_date="today"),
                "cashflow_type": random.choice(["PRINCIPAL", "INTEREST", "FEE", "DISBURSEMENT"]),
                "description": self.fake.sentence(nb_words=6)
            })
        self.data["cashflow"] = pd.DataFrame(cashflows)

        # 8. Deposit (Funding side)
        deposits = []
        for i in range(counts.get("deposit", 1000)):
            deposits.append({
                "deposit_id": ID_PATTERNS["deposit"].format(i+1),
                "customer_id": random.choice(cust_ids),
                "account_id": random.choice(acc_ids),
                "amount": round(random.uniform(10000, 1000000), 2),
                "deposit_date": self.fake.date_between(start_date="-3y", end_date="today")
            })
        self.data["deposit"] = pd.DataFrame(deposits)

        # Apply messiness to all
        for table in self.data:
            self.data[table] = self._inject_messiness(self.data[table], table)

        return self.data
