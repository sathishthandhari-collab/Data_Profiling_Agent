from typing import Dict, Any, List

# ID Patterns
ID_PATTERNS = {
    "branch": "BR-{:03d}",
    "customer": "CUST-{:05d}",
    "product": "PROD-{:03d}",
    "account": "ACC-{:06d}",
    "loan": "LOAN-{:06d}",
    "collateral": "COL-{:06d}",
    "cashflow": "CF-{:08d}",
    "deposit": "DEP-{:06d}"
}

# LoanIQ Product Types
PRODUCT_TYPES = [
    "Term Loan",
    "Revolving Credit",
    "Banker Acceptance",
    "Swing Line",
    "Letter of Credit",
    "Delayed Draw Term Loan",
    "Bridge Loan"
]

# Messiness Configuration (Percentages)
MESSINESS = {
    "null_pct": {
        "description": 0.15,  # 15% nulls in descriptions
        "collateral_value": 0.05,
        "tax_id": 0.10,
        "swift_code": 0.20
    },
    "outlier_pct": 0.01,  # 1% of numeric values will be outliers
    "outlier_multiplier": 50.0  # Outliers will be 50x the normal range
}

# Table Schemas (Metadata for Faker)
TABLE_SCHEMAS = {
    "branch": ["branch_id", "branch_name", "region", "swift_code"],
    "product": ["product_id", "product_name", "product_type", "base_rate"],
    "customer": ["customer_id", "full_name", "customer_type", "country", "tax_id", "email"],
    "account": ["account_id", "customer_id", "product_id", "branch_id", "currency", "credit_limit", "start_date"],
    "loan": ["loan_id", "account_id", "principal_amount", "interest_rate", "maturity_date", "status"],
    "deposit": ["deposit_id", "customer_id", "account_id", "amount", "deposit_date"],
    "collateral": ["collateral_id", "loan_id", "collateral_type", "estimated_value", "valuation_date"],
    "cashflow": ["cashflow_id", "loan_id", "amount", "cashflow_date", "cashflow_type", "description"]
}
