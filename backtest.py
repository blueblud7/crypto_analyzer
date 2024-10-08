import requests
import os
import pandas as pd
import tkinter as tk
from tkinter import ttk, messagebox
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import time
import numpy as np
import math

def fetch_coin_list():
    """Fetch the list of all available coins in the KRW market from Upbit."""
    url = "https://api.upbit.com/v1/market/all"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        krw_coins = [coin['market'] + ' (' + coin['korean_name'] + ')' for coin in data if coin['market'].startswith('KRW')]
        return krw_coins
    else:
        print(f"Failed to fetch coin list. Status code: {response.status_code}")
        return []

def fetch_historical_data(coin, count=200, to=None):
    """Fetch historical daily candlestick data for a specific coin from Upbit."""
    url = f"https://api.upbit.com/v1/candles/days?market={coin.split(' ')[0]}&count={count}"
    if to:
        url += f"&to={to}"

    retries = 3
    while retries > 0:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            df = pd.DataFrame(data)
            if not df.empty:
                df['candle_date_time_kst'] = pd.to_datetime(df['candle_date_time_kst'])
                return df[::-1]
            else:
                print(f"No data returned for {coin}.")
                return pd.DataFrame()
        elif response.status_code == 429:
            print(f"Rate limit exceeded for {coin}. Retrying after a short delay.")
            time.sleep(10)
            retries -= 1
        else:
            print(f"Failed to fetch data for {coin}. Status code: {response.status_code}")
            return pd.DataFrame()

def load_coin_data(coin):
    """Load historical data from CSV."""
    file_name = f"{coin.split(' ')[0]}_data.csv"
    if os.path.exists(file_name):
        df = pd.read_csv(file_name)
        df['candle_date_time_kst'] = pd.to_datetime(df['candle_date_time_kst'])
        return df
    else:
        print(f"No saved data found for {coin}.")
        return pd.DataFrame()

def save_coin_data(coin, df):
    """Save historical data for a coin to a CSV file."""
    file_name = f"{coin.split(' ')[0]}_data.csv"
    df.to_csv(file_name, index=False)

def update_all_coins():
    """모든 코인의 데이터를 다운로드 및 업데이트하는 함수"""
    coins = fetch_coin_list()
    for coin in coins:
        print(f"Updating {coin}...")
        existing_data = load_coin_data(coin)

        if existing_data.empty:
            print(f"Fetching all available data for {coin}.")
            new_data = fetch_historical_data(coin)
        else:
            last_date = existing_data['candle_date_time_kst'].max()
            new_data = fetch_historical_data(coin, to=last_date.strftime("%Y-%m-%dT%H:%M:%S"))

            if new_data.empty or 'candle_date_time_kst' not in new_data.columns:
                print(f"No new data for {coin}.")
                continue

            new_data = new_data[new_data['candle_date_time_kst'] > last_date]

        if not new_data.empty:
            updated_data = pd.concat([existing_data, new_data], ignore_index=True)
            save_coin_data(coin, updated_data)
            print(f"Data for {coin} has been updated.")
        else:
            print(f"No new data for {coin}.")

def load_saved_coins():
    """현재 디렉토리의 CSV 파일을 확인하여 저장된 코인 리스트를 반환합니다."""
    files = os.listdir()
    coin_files = [f.split('_data.csv')[0] for f in files if f.endswith('_data.csv')]
    return coin_files

def calculate_returns(df):
    """Calculate daily returns based on closing prices."""
    try:
        df['return'] = df['trade_price'].pct_change() * 100
    except KeyError:
        print(f"'trade_price' column not found in data. Skipping return calculation.")
    return df

def analyze_periodic_distribution(df, period):
    """Analyze the periodic return distribution (daily, weekly, or monthly) for a coin."""
    df['return'] = df['trade_price'].pct_change() * 100  # Calculate daily returns

    if period == 'daily':
        return df
    elif period == 'weekly':
        return df.resample('W-MON', on='candle_date_time_kst').last().pct_change()['trade_price'] * 100
    elif period == 'monthly':
        return df.resample('M', on='candle_date_time_kst').last().pct_change()['trade_price'] * 100

class CryptoApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Crypto Return Analysis")
        self.geometry("800x600")

        self.download_button = tk.Button(self, text="모든 코인 데이터 다운로드", command=self.download_all_data)
        self.download_button.pack(pady=10)

        self.coin_label = tk.Label(self, text="코인 선택")
        self.coin_label.pack()

        self.coin_var = tk.StringVar()
        self.coin_dropdown = ttk.Combobox(self, textvariable=self.coin_var)
        self.coin_dropdown.pack()

        self.period_label = tk.Label(self, text="주기 선택 (일별, 주별, 월별)")
        self.period_label.pack()

        self.period_var = tk.StringVar()
        self.period_dropdown = ttk.Combobox(self, textvariable=self.period_var, values=['daily', 'weekly', 'monthly'])
        self.period_dropdown.pack()

        self.analyze_button = tk.Button(self, text="분석 및 시각화", command=self.analyze_and_visualize)
        self.analyze_button.pack(pady=10)

        self.fig, self.ax = plt.subplots(figsize=(8, 6))
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack()

        self.update_coin_list()

    def download_all_data(self):
        update_all_coins()
        self.update_coin_list()
        messagebox.showinfo("완료", "모든 코인의 데이터가 성공적으로 다운로드되었습니다.")

    def update_coin_list(self):
        coins = load_saved_coins()
        if coins:
            self.coin_dropdown['values'] = coins
        else:
            messagebox.showwarning("경고", "저장된 코인 데이터가 없습니다. 먼저 데이터를 다운로드하세요.")

    def calculate_distribution(self, df, bin_size=1):
        """Calculate return distribution with fixed bin size."""
        if 'return' not in df.columns:
            print("No 'return' column found.")
            return pd.Series()

        min_return = math.floor(df['return'].min() / bin_size) * bin_size
        max_return = math.ceil(df['return'].max() / bin_size) * bin_size

        bins = np.arange(min_return, max_return + bin_size, bin_size)

        distribution, _ = np.histogram(df['return'], bins=bins, density=True)
        distribution = distribution * 100 * bin_size

        labels = [f"{b:.0f}%" if b == 0 else f"{b:+.0f}%" for b in bins[:-1]]

        return pd.Series(distribution, index=labels)

    def analyze_and_visualize(self):
        selected_coin = self.coin_var.get()
        selected_period = self.period_var.get()
    
        if not selected_coin or not selected_period:
            messagebox.showerror("입력 오류", "코인과 주기를 모두 선택하세요!")
            return
    
        df = load_coin_data(selected_coin)
    
        if df.empty:
            messagebox.showerror("데이터 오류", f"{selected_coin}의 데이터를 찾을 수 없습니다.")
            return
    
        df = analyze_periodic_distribution(df, selected_period)
    
        if df.empty:
            messagebox.showerror("데이터 오류", f"{selected_coin}의 {selected_period} 데이터를 찾을 수 없습니다.")
            return
    
        self.ax.clear()
        self.ax.set_title(f'{selected_coin} {selected_period.capitalize()} Return Distribution')
    
        distribution = self.calculate_distribution(df)
    
        if not distribution.empty:
            self.ax.bar(distribution.index, distribution.values, width=0.8, align='center', color="blue", alpha=0.7)
            self.ax.set_xticks(range(len(distribution.index)))
            self.ax.set_xticklabels(distribution.index, rotation=45, ha='right', fontsize=6)  # 수정된 부분
            self.ax.tick_params(axis='x', which='major', pad=0)  # x축 레이블과 축 사이의 간격 조정
        else:
            self.ax.text(0.5, 0.5, '데이터 없음', horizontalalignment='center', verticalalignment='center', transform=self.ax.transAxes)
    
        self.ax.set_xlabel('Return (%)')
        self.ax.set_ylabel('Proportion (%)')
    
        self.ax.set_xlim(left=-0.5, right=len(distribution.index)-0.5)
    
        plt.tight_layout()  # 그래프 레이아웃 자동 조정
        self.canvas.draw()

if __name__ == "__main__":
    app = CryptoApp()
    app.mainloop()
