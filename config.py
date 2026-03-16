# 파일명: config.py
import json
import os
import datetime
import pytz
import math
import time

# [V14.5] 파이썬 파일(.py)로 분리된 버전 히스토리를 모듈로 즉시 임포트합니다.
try:
    from version_history import VERSION_HISTORY
except ImportError:
    # version_history.py 파일이 누락되었을 경우를 대비한 안전 장치
    VERSION_HISTORY = [
        "V14.x [-] 버전 기록 파일(version_history.py)을 찾을 수 없습니다."
    ]

class ConfigManager:
    def __init__(self):
        # [V14.2] 모든 데이터/설정 파일이 data/ 디렉토리 내부에서 생성되고 관리되도록 경로 수정
        self.FILES = {
            "TOKEN": "data/token.dat",
            "CHAT_ID": "data/chat_id.dat",
            "LEDGER": "data/manual_ledger.json",    
            "HISTORY": "data/manual_history.json",  
            "SPLIT": "data/split_config.json",
            "TICKER": "data/active_tickers.json",
            "TURBO": "data/turbo_mode.dat",
            "PROFIT_CFG": "data/profit_config.json",
            "LOCKS": "data/trade_locks.json",
            "SEED_CFG": "data/seed_config.json",         
            "COMPOUND_CFG": "data/compound_config.json",
            "VERSION_CFG": "data/version_config.json",
            "REVERSE_CFG": "data/reverse_config.json" # [V14.1 리버스모드] 상태 보관용 파일 추가
        }
        
        self.DEFAULT_SEED = {"SOXL": 6720.0, "TQQQ": 6720.0}
        self.DEFAULT_SPLIT = {"SOXL": 40.0, "TQQQ": 40.0}
        self.DEFAULT_TARGET = {"SOXL": 12.0, "TQQQ": 10.0}
        self.DEFAULT_COMPOUND = {"SOXL": 70.0, "TQQQ": 70.0}
        self.DEFAULT_VERSION = {"SOXL": "V14", "TQQQ": "V14"} 

    def _load_json(self, filename, default=None):
        if os.path.exists(filename):
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return default if default is not None else {}

    def _save_json(self, filename, data):
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_file(self, filename, default=None):
        if os.path.exists(filename):
            try:
                with open(filename, 'r') as f:
                    return f.read().strip()
            except:
                pass
        return default

    def _save_file(self, filename, content):
        with open(filename, 'w') as f:
            f.write(str(content))

    def get_ledger(self):
        return self._load_json(self.FILES["LEDGER"], [])

    # 🚀 [V15.1] T값 산출 절대 공식: (총 매수액 / 1회분)
    def calculate_v15_t_val(self, ticker):
        recs = [r for r in self.get_ledger() if r['ticker'] == ticker]
        total_buy_amt = sum(r['price'] * r['qty'] for r in recs if r['side'] == 'BUY')
        
        seed = self.get_seed(ticker)
        split = self.get_split_count(ticker)
        one_portion = seed / split if split > 0 else 1
        
        t_val = total_buy_amt / one_portion
        return round(t_val, 4)

    # 🚀 [V15.3] 제네시스 장부 캐싱
    def overwrite_genesis_ledger(self, ticker, genesis_records, actual_avg):
        ledger = self.get_ledger()
        remaining = [r for r in ledger if r['ticker'] != ticker]
        
        for i, rec in enumerate(genesis_records):
            remaining.append({
                "id": i + 1,
                "date": rec['date'],
                "ticker": ticker,
                "side": rec['side'],
                "price": rec['price'],
                "qty": rec['qty'],
                "avg_price": actual_avg, 
                "exec_id": f"GENESIS_{int(time.time())}_{i}",
                "is_reverse": False 
            })
        self._save_json(self.FILES["LEDGER"], remaining)

    # 🚀 [V15.5] 증분 업데이트 (1일 치만 교체하여 덮어쓰기)
    def overwrite_incremental_ledger(self, ticker, temp_recs, new_today_records):
        ledger = self.get_ledger()
        remaining = [r for r in ledger if r['ticker'] != ticker]
        updated_ticker_recs = list(temp_recs)
        
        current_rev_state = self.get_reverse_state(ticker).get("is_active", False)
        max_id = max([r.get('id', 0) for r in ledger] + [0])
        
        for i, rec in enumerate(new_today_records):
            max_id += 1
            updated_ticker_recs.append({
                "id": max_id,
                "date": rec['date'],
                "ticker": ticker,
                "side": rec['side'],
                "price": rec['price'],
                "qty": rec['qty'],
                "avg_price": rec['avg_price'],
                "exec_id": f"FASTTRACK_{int(time.time())}_{i}",
                "is_reverse": current_rev_state
            })
            
        remaining.extend(updated_ticker_recs)
        self._save_json(self.FILES["LEDGER"], remaining)

    # [V15] 로직 1-A / 1-B: 장부를 현재 잔고로 강제 덮어쓰기
    def overwrite_ledger(self, ticker, actual_qty, actual_avg):
        ledger = self.get_ledger()
        remaining = [r for r in ledger if r['ticker'] != ticker]
        
        kst = pytz.timezone('Asia/Seoul')
        today_str = datetime.datetime.now(kst).strftime('%Y-%m-%d')
        new_id = 1 if not remaining else max(r.get('id', 0) for r in remaining) + 1
        
        remaining.append({
            "id": new_id, "date": today_str, "ticker": ticker, "side": "BUY",
            "price": actual_avg, "qty": actual_qty, "avg_price": actual_avg, 
            "exec_id": f"INIT_{int(time.time())}", "desc": "초기동기화", "is_reverse": False
        })
        self._save_json(self.FILES["LEDGER"], remaining)

    # 🔥 [V16.0] 사용되지 않는 구형 V13/V14 동기화 함수들(sync_from_balance, append_ledger_record, get_realized_pnl) 전면 삭제 완료

    def clear_ledger_for_ticker(self, ticker):
        ledger = self.get_ledger()
        remaining = [r for r in ledger if r['ticker'] != ticker]
        self._save_json(self.FILES["LEDGER"], remaining)
        # [V14.1 리버스모드] 졸업 시 리버스모드 상태도 초기화
        self.set_reverse_state(ticker, False, 0, 0.0)

    def calculate_holdings(self, ticker, records=None):
        if records is None:
            records = self.get_ledger()
        target_recs = [r for r in records if r['ticker'] == ticker]
        total_qty, total_invested, total_sold = 0, 0.0, 0.0    
        
        for r in target_recs:
            if r['side'] == 'BUY':
                total_qty += r['qty']
                total_invested += (r['price'] * r['qty'])
            elif r['side'] == 'SELL':
                total_qty -= r['qty']
                total_sold += (r['price'] * r['qty'])
        
        total_qty = max(0, int(total_qty))
        invested_up = math.ceil(total_invested * 100) / 100.0
        sold_up = math.ceil(total_sold * 100) / 100.0
        
        avg_price = 0.0
        if total_qty > 0 and target_recs:
            # 💡 [V15.4 버그 수정] 단순 계산이 아닌 장부 최신 기록에 보존된 KIS의 절대 평단가를 그대로 가져옴!
            avg_price = float(target_recs[-1].get('avg_price', 0.0))
            
            # (과거 버전 호환성을 위해 avg_price가 없을 경우에만 기존 방식으로 비상 계산)
            if avg_price == 0.0:
                buy_sum = sum(r['price']*r['qty'] for r in target_recs if r['side']=='BUY')
                buy_qty = sum(r['qty'] for r in target_recs if r['side']=='BUY')
                if buy_qty > 0:
                    avg_price = buy_sum / buy_qty
        
        return total_qty, avg_price, invested_up, sold_up

    # [V14.1 리버스모드] 리버스 상태 조회 및 설정
    def get_reverse_state(self, ticker):
        d = self._load_json(self.FILES["REVERSE_CFG"], {})
        # [V14.9] 탈출 목표(exit_target) 값 추가 기본값 0.0
        return d.get(ticker, {"is_active": False, "day_count": 0, "exit_target": 0.0})

    def set_reverse_state(self, ticker, is_active, day_count, exit_target=0.0):
        d = self._load_json(self.FILES["REVERSE_CFG"], {})
        d[ticker] = {"is_active": is_active, "day_count": day_count, "exit_target": exit_target}
        self._save_json(self.FILES["REVERSE_CFG"], d)

    # [V14] 무매 버전4의 핵심: 실시간 동적 1회분 계산 로직
    def calculate_v14_state(self, ticker):
        ledger = self.get_ledger()
        target_recs = sorted([r for r in ledger if r['ticker'] == ticker], key=lambda x: x.get('id', 0))
        
        seed = self.get_seed(ticker)
        split = self.get_split_count(ticker)
        
        holdings = 0
        t_val = 0.0
        rem_cash = seed
        
        for r in target_recs:
            if holdings == 0:
                t_val = 0.0
                rem_cash = seed
                
            qty = r['qty']
            price = r['price']
            amt = qty * price
            
            is_rec_rev = r.get('is_reverse', False) 
            
            if r['side'] == 'BUY':
                if holdings == 0 and 'SYNC' in str(r.get('exec_id', '')):
                    t_val = amt / (seed / split) if split > 0 else 0
                    rem_cash -= amt
                else:
                    if is_rec_rev:
                        t_val += (split - t_val) * 0.25
                        rem_cash -= amt
                    else:
                        budget_of_day = rem_cash / (split - t_val) if (split - t_val) > 0 else rem_cash
                        t_val += (amt / budget_of_day) if budget_of_day > 0 else 0
                        rem_cash -= amt
                holdings += qty
                
            elif r['side'] == 'SELL':
                if qty >= holdings: 
                    holdings = 0
                    t_val = 0.0
                    rem_cash = seed
                else: 
                    holdings -= qty
                    if is_rec_rev:
                        multiplier = 0.9 if split <= 20 else 0.95
                        t_val *= multiplier
                    else:
                        t_val *= 0.75
                    # 🔥 [V15.5] 대표님 지시 반영: 매도 금액을 남은 시드(예산)에 복원하여 T값과 1회분이 
                    # 고정되지 않고 완벽한 비율로 동적 계산되도록 하는 무매 V4의 신의 한 수!
                    rem_cash += amt
                    
        if holdings > 0:
            current_budget = rem_cash / (split - t_val) if (split - t_val) > 0 else rem_cash
        else:
            current_budget = seed / split
            t_val = 0.0
            
        return max(0.0, round(t_val, 4)), max(0.0, current_budget), max(0.0, rem_cash)

    # 🚀 [V16.0] 부활! 졸업 시 명예의 전당 저장 및 복리 계산 로직
    def archive_graduation(self, ticker, end_date, prev_close=0.0):
        ledger = self.get_ledger()
        target_recs = [r for r in ledger if r['ticker'] == ticker]
        if not target_recs:
            return None, 0
        
        ledger_qty, avg_price, _, _ = self.calculate_holdings(ticker, target_recs)
        
        if ledger_qty > 0:
            split = self.get_split_count(ticker)
            is_reverse = self.get_reverse_state(ticker).get("is_active", False)

            if is_reverse:
                divisor = 10 if split <= 20 else 20
                loc_qty = math.floor(ledger_qty / divisor)
            else:
                loc_qty = math.ceil(ledger_qty / 4)

            limit_qty = ledger_qty - loc_qty
            if limit_qty < 0: 
                loc_qty = ledger_qty
                limit_qty = 0

            target_ratio = self.get_target_profit(ticker) / 100.0
            target_price = math.ceil(avg_price * (1 + target_ratio) * 100) / 100.0
            loc_price = prev_close if prev_close > 0 else avg_price

            new_id = max((r.get('id', 0) for r in ledger), default=0) + 1

            if loc_qty > 0:
                rec_loc = {"id": new_id, "date": end_date, "ticker": ticker, "side": "SELL", "price": loc_price, "qty": loc_qty, "avg_price": avg_price, "exec_id": f"GRAD_LOC_{int(time.time())}", "is_reverse": is_reverse}
                ledger.append(rec_loc)
                target_recs.append(rec_loc)
                new_id += 1

            if limit_qty > 0:
                rec_limit = {"id": new_id, "date": end_date, "ticker": ticker, "side": "SELL", "price": target_price, "qty": limit_qty, "avg_price": avg_price, "exec_id": f"GRAD_LMT_{int(time.time())}", "is_reverse": is_reverse}
                ledger.append(rec_limit)
                target_recs.append(rec_limit)

            self._save_json(self.FILES["LEDGER"], ledger)

        total_buy = math.ceil(sum(r['price']*r['qty'] for r in target_recs if r['side']=='BUY') * 100) / 100.0
        total_sell = math.ceil(sum(r['price']*r['qty'] for r in target_recs if r['side']=='SELL') * 100) / 100.0
        
        profit = math.ceil((total_sell - total_buy) * 100) / 100.0
        yield_pct = math.ceil(((profit / total_buy * 100) if total_buy > 0 else 0.0) * 100) / 100.0
        
        compound_rate = self.get_compound_rate(ticker) / 100.0
        added_seed = 0
        if profit > 0 and compound_rate > 0:
            added_seed = math.floor(profit * compound_rate)
            current_seed = self.get_seed(ticker)
            self.set_seed(ticker, current_seed + added_seed)

        history = self._load_json(self.FILES["HISTORY"], [])
        new_hist = {
            "id": len(history) + 1, "ticker": ticker, "end_date": end_date,
            "profit": profit, "yield": yield_pct, "revenue": total_sell, "invested": total_buy, "trades": target_recs
        }
        history.append(new_hist)
        self._save_json(self.FILES["HISTORY"], history)
        
        self.clear_ledger_for_ticker(ticker)
        
        return new_hist, added_seed

    # [V14.5] 파이썬 모듈에서 리스트를 그대로 읽어옵니다.
    def get_version_history(self):
        return VERSION_HISTORY

    # 🚀 [V15.5] 1줄 버전 문자열 파싱 호환성 추가
    def get_latest_version(self):
        history = self.get_version_history()
        if history and len(history) > 0:
            if isinstance(history[0], str):
                return history[0].split(' ')[0] # "V15.5" 부분만 추출
            return history[0].get("version", "V14.x")
        return "V14.x"

    def get_history(self):
        return self._load_json(self.FILES["HISTORY"], [])

    def check_lock(self, ticker, market_type):
        est = pytz.timezone('US/Eastern')
        today = datetime.datetime.now(est).strftime('%Y-%m-%d')
        locks = self._load_json(self.FILES["LOCKS"], {})
        return locks.get(f"{today}_{ticker}_{market_type}", False)

    def set_lock(self, ticker, market_type):
        est = pytz.timezone('US/Eastern')
        today = datetime.datetime.now(est).strftime('%Y-%m-%d')
        locks = self._load_json(self.FILES["LOCKS"], {})
        locks[f"{today}_{ticker}_{market_type}"] = True
        self._save_json(self.FILES["LOCKS"], locks)

    def reset_locks(self):
        self._save_json(self.FILES["LOCKS"], {})
    
    def get_seed(self, t):
        return float(self._load_json(self.FILES["SEED_CFG"], self.DEFAULT_SEED).get(t, 6720.0))

    def set_seed(self, t, v): 
        d = self._load_json(self.FILES["SEED_CFG"], self.DEFAULT_SEED)
        d[t] = v
        self._save_json(self.FILES["SEED_CFG"], d)

    def get_compound_rate(self, t):
        return float(self._load_json(self.FILES["COMPOUND_CFG"], self.DEFAULT_COMPOUND).get(t, 70.0))

    def set_compound_rate(self, t, v):
        d = self._load_json(self.FILES["COMPOUND_CFG"], self.DEFAULT_COMPOUND)
        d[t] = v
        self._save_json(self.FILES["COMPOUND_CFG"], d)

    def get_version(self, t):
        return self._load_json(self.FILES["VERSION_CFG"], self.DEFAULT_VERSION).get(t, "V14")

    def set_version(self, t, v):
        d = self._load_json(self.FILES["VERSION_CFG"], self.DEFAULT_VERSION)
        d[t] = v
        self._save_json(self.FILES["VERSION_CFG"], d)

    def get_split_count(self, t):
        return self._load_json(self.FILES["SPLIT"], self.DEFAULT_SPLIT).get(t, 40.0)

    def get_target_profit(self, t):
        return self._load_json(self.FILES["PROFIT_CFG"], self.DEFAULT_TARGET).get(t, 10.0)

    def get_turbo_mode(self):
        return self._load_file(self.FILES["TURBO"]) == 'True'

    def set_turbo_mode(self, v):
        self._save_file(self.FILES["TURBO"], str(v))

    def get_active_tickers(self):
        return self._load_json(self.FILES["TICKER"], ["SOXL", "TQQQ"])

    def set_active_tickers(self, v):
        self._save_json(self.FILES["TICKER"], v)

    def get_chat_id(self): 
        v = self._load_file(self.FILES["CHAT_ID"])
        return int(v) if v else None

    def set_chat_id(self, v):
        self._save_file(self.FILES["CHAT_ID"], v)
