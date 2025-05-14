import pandas as pd
import unicodedata, re

def clean_text(x):
    if pd.isna(x):
        return ''
    x = unicodedata.normalize('NFKD', str(x)).encode('ascii', 'ignore').decode('utf-8')
    x = re.sub(r'\s+', ' ', x)
    return x.strip().upper()