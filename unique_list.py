import pandas as pd
import glob
import os

# 1. Find all CSV files
csv_files = glob.glob('./list/*.csv')

# 2. Read and combine them into a single DataFrame
df_list = [pd.read_csv(file) for file in csv_files]
combined_df = pd.concat(df_list, ignore_index=True)

# 3. Drop duplicate rows
combined_df = combined_df.drop_duplicates()

# 4. Create output directory if not exists
output_dir = './output'
os.makedirs(output_dir, exist_ok=True)

# 5. Split into multiple files with less than 200 rows each
chunk_size = 200
for i in range(0, len(combined_df), chunk_size):
    chunk = combined_df.iloc[i:i + chunk_size]
    chunk_file = os.path.join(output_dir, f'output_part_{i//chunk_size + 1}.csv')
    chunk.to_csv(chunk_file, index=False)

print("Done! Files split and saved.")
