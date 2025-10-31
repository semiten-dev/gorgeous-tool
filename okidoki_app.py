# okidoki_app.py
from flask import Flask, render_template, request, session, redirect, url_for
import os

app = Flask(__name__)
app.secret_key = os.urandom(24) 

# --- 定数 ---
COST_PER_GAME_NET = 50.0 / 32.0   # (1.5625) 差枚計算用
COST_PER_GAME_GROSS = 3.0       # (3.0) 機械割計算用
BIG_BONUS_GAMES = 59
REG_BONUS_GAMES = 24
AVG_BB_PAYOUT = 210
AVG_RB_PAYOUT = 90
TARGET_SASHIMAI = -1500.0       # ★追加 (要望2)
# -----------------------------------

# ★★★★★ 「機械割(wari)」と「到達G数」の計算ロジックを修正 ★★★★★
def calculate_current_state(history, current_games_input):
    total_bb_payout = 0
    total_rb_payout = 0
    total_games_net = 0.0     # 差枚計算用 (ボーナス間G数)
    total_games_bonus = 0.0   # 機械割計算用 (ボーナス中G数)

    try:
        # 1. 履歴からG数と払出を集計
        for item in history:
            total_games_net += item['games_at']
            if item['type'] == 'BIG':
                total_bb_payout += item['payout']
                total_games_bonus += BIG_BONUS_GAMES
            elif item['type'] == 'REG':
                total_rb_payout += item['payout']
                total_games_bonus += REG_BONUS_GAMES
        
        # 2. 「現在のG数」も加算
        current_games = 0.0
        if current_games_input:
            current_games = float(current_games_input)
        total_games_net += current_games
        
        # --- 差枚計算 (Netコストベース) ---
        total_out_bonus_only = total_bb_payout + total_rb_payout
        total_in_net = total_games_net * COST_PER_GAME_NET
        sashimai = total_out_bonus_only - total_in_net 
        
        # --- ★★★★★ 修正後の機械割計算 ★★★★★
        # 総投入 (Gross IN) = (ボーナス間G * 3) + (ボーナス中G * 3)
        total_in_gross = (total_games_net + total_games_bonus) * COST_PER_GAME_GROSS
        
        # 総払出 (Gross OUT) = (ボーナス払出) + (ボーナス間Gの小役払出) + (ボーナス中Gの払出)
        # (ボーナス間Gの小役払出 = ボーナス間G * (3.0 - 1.5625))
        small_payouts_net = total_games_net * (COST_PER_GAME_GROSS - COST_PER_GAME_NET)
        # (ボーナス中Gの払出 = ボーナス中G * 3.0)
        payouts_bonus_g = total_games_bonus * COST_PER_GAME_GROSS
        
        total_out_gross = total_out_bonus_only + small_payouts_net + payouts_bonus_g
        
        wari = 0.0
        if total_in_gross > 0:
            wari = (total_out_gross / total_in_gross) * 100.0
        # --- (機械割 修正ここまで) ---
        
        # --- ★★★★★ 到達G数計算 (要望2) ★★★★★
        games_to_target_str = ""
        if sashimai >= TARGET_SASHIMAI:
            # (例: -1400 >= -1500) -> 差枚が-1500より良い場合
            coins_to_lose = sashimai - TARGET_SASHIMAI # (例: -1400 - (-1500) = 100)
            games_needed = coins_to_lose / COST_PER_GAME_NET # (例: 100 / 1.5625 = 64)
            games_to_target_str = f"{TARGET_SASHIMAI:.0f}枚まで あと {games_needed:.0f} G"
        else:
            # (例: -1600 < -1500) -> 差枚が-1500より悪い場合
            games_to_target_str = f"{TARGET_SASHIMAI:.0f}枚 到達済み"
        # --- (到達G数 修正ここまで) ---
        
        return {
            'total_in': total_in_net, 'total_out': total_out_bonus_only, 'sashimai': sashimai,
            'wari': wari, 'bb_total': total_bb_payout, 'rb_total': total_rb_payout,
            'games': total_games_net,
            'games_to_target_str': games_to_target_str # ★追加
        }
    except ValueError:
        return { 'error': 'G数に数値を入力してください' }
    except Exception as e:
        return { 'error': f'計算エラー: {e}' }


# ★★★★★ 「機械割(wari_at_point)」の計算ロジックを修正 ★★★★★
@app.route('/')
def index():
    history = session.get('history', [])
    current_games_input = session.get('current_games_input', "0")
    
    state = calculate_current_state(history, current_games_input)

    display_history = []
    running_total_out_bonus_only = 0.0
    running_total_games_net = 0.0     # 差枚・小役計算用
    running_total_games_bonus = 0.0   # 機械割のボーナスG用
    running_total_games_display = 0.0 # 累計G表示用
    
    for item in history:
        # 1. 差枚計算 (Net)
        running_total_games_net += item['games_at']
        running_total_out_bonus_only += item['payout']
        total_in_net_at_point = running_total_games_net * COST_PER_GAME_NET
        sashimai_at_point = running_total_out_bonus_only - total_in_net_at_point
        
        # 2. 累計G表示 (Gross) と 機械割のボーナスG
        cumulative_g_start = running_total_games_display + item['games_at']
        if item['type'] == 'BIG':
            running_total_games_bonus += BIG_BONUS_GAMES
            cumulative_g_end = cumulative_g_start + BIG_BONUS_GAMES
        elif item['type'] == 'REG':
            running_total_games_bonus += REG_BONUS_GAMES
            cumulative_g_end = cumulative_g_start + REG_BONUS_GAMES
        
        # --- ★★★★★ 修正後の機械割計算 (履歴用) ★★★★★
        total_in_gross = (running_total_games_net + running_total_games_bonus) * COST_PER_GAME_GROSS
        small_payouts_net = running_total_games_net * (COST_PER_GAME_GROSS - COST_PER_GAME_NET)
        payouts_bonus_g = running_total_games_bonus * COST_PER_GAME_GROSS
        total_out_gross = running_total_out_bonus_only + small_payouts_net + payouts_bonus_g
        
        wari_at_point = 0.0
        if total_in_gross > 0:
            wari_at_point = (total_out_gross / total_in_gross) * 100.0
        # --- (機械割 修正ここまで) ---

        # 4. HTMLに渡す
        new_item = item.copy()
        new_item['sashimai_at_point'] = sashimai_at_point
        new_item['wari_at_point'] = wari_at_point
        new_item['cumulative_g_start'] = cumulative_g_start
        new_item['cumulative_g_end'] = cumulative_g_end
        
        display_history.append(new_item)
        
        running_total_games_display = cumulative_g_end

    # 5. 「現在のG数」の行を追加 (機械割も修正)
    try:
        current_g_val = int(current_games_input)
        if current_g_val > 0:
            current_sashimai = state.get('sashimai', 0.0)
            current_wari = state.get('wari', 0.0)
            cumulative_g_start = running_total_games_display + current_g_val
            
            current_item = {
                'games_at': current_g_val, 'type': '現在', 'payout': '---',
                'sashimai_at_point': current_sashimai,
                'wari_at_point': current_wari,
                'cumulative_g_start': cumulative_g_start,
                'cumulative_g_end': None
            }
            display_history.append(current_item)
    except (ValueError, TypeError):
        pass

    return render_template('okidoki_index.html', 
                           history=display_history,
                           state=state,
                           current_games_input=current_games_input)

# ★★★★★ 「自動入力」ロジック (変更なし) ★★★★★
@app.route('/add_bonus', methods=['POST'])
def add_bonus():
    try:
        bonus_type = request.form['bonus_type']
        games_at = request.form['games_at']
        
        payout_str = request.form['payout']
        payout = 0
        
        if not payout_str: # 空欄の場合
            if bonus_type == 'BIG':
                payout = AVG_BB_PAYOUT
            elif bonus_type == 'REG':
                payout = AVG_RB_PAYOUT
        else:
            payout = int(payout_str)
            
        new_bonus = {
            'type': bonus_type,
            'games_at': int(games_at),
            'payout': payout
        }
        
        history = session.get('history', [])
        history.append(new_bonus)
        session['history'] = history
        session['current_games_input'] = "0"
        
    except ValueError:
        pass 
    return redirect(url_for('index'))

# (update_games 関数は変更なし)
@app.route('/update_games', methods=['POST'])
def update_games():
    session['current_games_input'] = request.form['current_games']
    return redirect(url_for('index'))

# (reset 関数は変更なし)
@app.route('/reset')
def reset():
    session.pop('history', None)
    session.pop('current_games_input', None)
    return redirect(url_for('index'))

# ★★★★★ 「直近1件を削除」機能 (変更なし) ★★★★★
@app.route('/delete_last')
def delete_last():
    history = session.get('history', [])
    if history: 
        history.pop() 
        session['history'] = history
    session['current_games_input'] = "0"
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
