import os
from teshq.api import TeshQuery

def main():
    print("🚀 Initializing TeshQuery SDK...")
    client = TeshQuery()

    print("\n📊 Executing natural language query using the default query() method...")
    # By default, query() now returns a pandas DataFrame!
    df = client.query("list out top 3 customers by their names alphabetically")

    print("\n✅ Results (Pandas DataFrame):")
    print("-" * 40)
    print(df)
    
    print("\n💾 Exporting to CSV using output_format='csv'...")
    # You can instantly save to CSV
    csv_path = client.query(
        "count the number of customers", 
        output_format="csv", 
        output_path="customer_count.csv"
    )
    print(f"Saved directly to: {csv_path}")
    
    print("\n💾 Exporting to Excel using output_format='excel'...")
    # You can also instantly save to Excel
    excel_path = client.query(
        "list out top 3 customers by their names alphabetically", 
        output_format="excel", 
        output_path="top_customers.xlsx"
    )
    print(f"Saved directly to: {excel_path}")
    
    print("\n📋 Returning standard dictionary format...")
    # Or fall back to dictionaries if needed
    results = client.query("list out top 3 customers", output_format="dict")
    print(type(results), "->", results[0])

if __name__ == "__main__":
    main()
