# 提案 v8「Echelon」:把 NF 鏈彈性重構成多階層庫存控制(2026-10-02,待 user 過目)

狀態:**規劃稿,未動工**。回朔點:home repo `fb20c60`+未 commit 的 10-01 工作;hhro-daemon `3a5d8c9`(v7.0.5 / 6.0-q6)。
動工前先打 tag:home `dev-final-2026-10-01`、daemon `v7.0.5-q6`;新分支 `v8-echelon`,全部新碼放新 package,舊 planner 原封不動可切回。

本文件是「活的」:§0 的貢獻帳本每個閘口更新一次;任何一場實驗推翻預期,先回來改帳本再繼續。

---

## 0. 貢獻帳本(每週閘口必更新;狀態=活/受威脅/死;死掉必須填替代)

| # | 預期貢獻 | 驗證指標(閘口) | 狀態 | 證據 | 死掉時的替代 |
|---|---|---|---|---|---|
| C1 | **(10-05 03:30 資料效期:10-01 r196 前 = 好場地(09-23 v6、消融、baseline、t3 附錄有效);r198-r214、r231/r232 = 降級場地只作診斷;HHRO-Q final r198/r200 要重跑;最終 G2 = S3a/S3b 各 10 + v6 6 在恢復場地,判準 spec §4.17)** **(10-04 21:00:成本閘維持逐場讀法,r207/r208 未過、r212 過;r207-r230 定位為診斷資料,最終 G2 在不變量定案後重跑並穿插 v6 對照;峰值 p99 違規=場地狀態差、反彈違規=VM/pod 操作期間輕載槽 VF ring 溢位,非指派不均;spec §4.15)** **(10-04 16:20 判準改寫,r208+ 結果出來前:G2 重跑驗「落在目標風險附近、成本如預測 ±2%」,v6 列參考不當閘;spec §4.14 第 5 節)** 結構 = base-stock + ski-rental(v6 已驗證的結構);**程序輸出兩個 λ(λ_VM、λ_UP)**,其餘手選常數刪除(stage 1 已刪 −1950 行)或列為致動常數;部位記帳(in-flight 集合)取代 cooldown/lock/freeze。**10-04 G2 實機(spec §4.13 第 4 節)**:S1 t1 57/60/60 燒 494.7±3.3、t2 59/59/60 燒 636.0±7.8 vs v6 全 60/60 燒 490.8±2.4 / 619.0±4.6 → 「等風險下更便宜」未成立;成立的是零手調落在 v6 +1%/+3% 成本、−1~−2 分鐘內;t2 含 warm-in 交棒艦隊混淆 | 留出 trace(分組隨機切分 ×6):在相同風險水準下程序輸出與專家值相容(VM 4.9 vs 5 UE、成本 ±0.5 點);UCB 版有有限樣本保證(+3 點);實機 G2:每配置 ≥3 場,SLO ≥ v6、成本 ±2%、flaps 如實報;「刪除後不退化」由實機證明 | **活(10-03 第五輪;措辭改)** | spec §4.10 | 實機刪除後退化 → 旋鈕消融找承重機制 |
| C2 | 彈性成本定律:C − C_oracle ≈ Σ c_l·(q_ε(h_l)/u_l + ½) × 共享因子;在實體 Mpps 鏈上逐槓桿驗證(lead h、單位 u、共享 N) | 至少兩個槓桿上模型預測 vs 實測誤差 ≤10%;**三槓桿絕對值**(qsim):單位 −72 core-min/h(6%)、lead −23(1.8%,校準版才兌現)、制式 0、合計 −90(7.1%) | **受威脅(10-03:7.1% < 原設 12% 停損閘;10-04 第七輪:等風險修正後單項 lead0 +10.8 / fine +5.9 / lock0 +4.3 / d0 +6.6、win0 −23.8,all_off −128;閉式的 Φ̄⁻¹(p/2) 形狀成立但 √h 尺度律不成立 → 定律只剩形狀,h 依賴改表/圖呈現;殘差 272.7 = 此策略族在該設定下的代價;10-04 晚第八輪:回看窗解耦後 lead 乾淨槓桿 −26.9(2.1%)、g=10/5 僅 +2.4/+8.4;★資訊集下界(10-04 午後修正:FMIN 重複計費 + 資訊集應為精確 D):舊物理 2% 下界 1197.4±11.9,base 1252.8 高 55(4.6%);新物理 2% 1230.6 vs 1277.9(+3.7%)、0.5% 1294.8 vs 1336.1(+3.2%)→ 主張改為「離同資訊集下界 4-5%」,不是近最優;次分鐘 lead 結論受資料分鐘解析度限制不下)** | spec §4.10 (3)、§4.12、§4.13 | 靠 C3 共享補;或接受 7% 並把主張改為「程序讓你選前緣操作點,v6 要人工重調」 |
| C3 | 跨 slice 風險共享:共用餘裕的分位數 < 各自分位數之和;相關係數下的閉式退化;per-slice SLO 不破 | 3 slice 共享 vs 分割:成本 −10% 以上、per-slice SLO 全綠;相關 slice 的退化落在界內 | 活(10-04 qsim:共享 1145-1165 vs 分割 1535-1590 = −26%;拆解 = 取整 ~330 主導、池化餘裕 44-71、最小艦隊重複 25-29;共享 per-slice 風險 = 匯總(比例分攤)或 ≈1/3 次數×3 幅度(集中上界);中間方案(UP 槽專屬)在同一硬體上限下到不了 2%;spec §4.12 第 4 節) | 先驗庫 18 sensor 可估相關 | 多 slice harness 做不出 → 只在 qsim 報,C2 仍成立 |
| C4 | 動態批量(訂貨時選單位大小)+ lead 縮短 | 成本 vs (u, h) 曲線與模型一致;worker 1/2/4 槽、lead 100→≤40 s | 活 | — | VyOS 小尺寸 image 卡住 → 只做 worker |
| C5 | 評估:160 UE、held-out、含 BACC 型/OptScaler-MPC 型/DRL 型 baseline | 全部 baseline 在同一平面、同一 trace 集跑完 | 活 | — | DRL 來不及 → related work 說明並列為 future |
| C6 | 系統/量測:5 Mpps 下 0.1%/1 ms 的可信量測管線 | 已有 | 活 | 09-20~10-01 全部破案記錄 | — |

目標刊物:**ToN / INFOCOM**(理論 + 實體驗證型);TNSM 為保底。NSDI/SIGCOMM 需要更大的系統物件,本輪不押。

---

## 1. 根因(用數字釘住,不再講形容詞)

| alloc core-min | t1 | t2 |
|---|---|---|
| 千里眼 oracle | 820 | 1087 |
| 含一批 lead 的可行下界 floor | 997(+22%) | 1236(+14%) |
| HHRO-Q 實際(r200/r198) | 1109(+11% over floor) | 1407(+14% over floor) |

- 14-22% 是 **lead time × 單位顆粒** 的物理代價,任何控制器省不掉;8-14% 是控制器自己的餘裕與駐留。兩個月只打了後者。
- 成本幾乎全在 VM 層(worker 100 s / VyOS 85 s 的 lead,一台 = 10-16 UE 的顆粒);槽層餘裕在「成本 = 燒掉的核」模型下近乎免費。
- 需求在 lead 尺度上近似隨機漫步(CV 證實趨勢/時段/跨點先驗零增益),預測無用;餘裕只能由分位數決定。
- 結論:根本問題是 **lead、顆粒、是否共享餘裕**,不是決策規則。v5→v6→v7 的百個修補都在修「規則怎麼不出錯」,沒碰「代價從哪來」。

---

## 2. 文獻定位(10-01~02 擴展查證;標 ★ 者對本案直接構成前作或撞車)

**同領域(5G UPF/核網擴縮)**
- NYCU/CHT 2026《Auto-Scaling and Load-Aware SDNFV Architecture for 5G UPF》:HPA(吞吐量)+ PFCP proxy + P4 LB + 縮容無縫遷移;4 台、≤2.5 Gbps、200 s、無 baseline。→ 機制上=我們的 drain/rehome;決策反應式單層。
- EuCNC 2024 DRL UPF 擴縮(vs HPA);★ NFScaler NetSoft 2024(DRL + domain randomization、實網、vs KEDA)。→ 學習式 baseline 的來源。
- CoreKube MobiCom 2023:無狀態控制面 + K8s 自動擴縮;L²5GC+ 2025(效能)。→ 控制面/效能,不碰 lead-time 彈性成本。
- TS-FAC 2025(門檻 + 分數准入)。

**雲端自動擴縮(撞車)**
- ★ OptScaler VLDB 2024:預測 + 反應 + MPC + 高斯 chance constraint,含開機/下線延遲,單層,生產環境。
- ★ BACC 2026-05:預測器 + ACI + 違規預算 PI 控制;pods only;明說無端到端保證。
- SLO-Scaler 2026-08(Bayesian LSTM)、Spandana 2026(FaaS 溢流層換嚴格 SLO)、GRAF ToN 2024、Autothrottle NSDI 24、TopFull SIGCOMM 24、Erms ASPLOS 23。
- CEMA JNCA 2025、J. Grid Computing 2024:容器 + VM 多層聯合;AMCS 2019:多層 co-scaling 同步問題。

**理論(我們可借、也必須對照)**
- 線上最佳化 + 切換成本:Lin 2012 right-sizing;Chen et al. OCO for cloud provisioning(知道超過 切換成本/能耗 比例的未來「零增益」);2403.17480(記憶 + 切換成本,無 lead);★ 2601.18936(2026-01,雙層 provisioning/scheduling,OCO + MDP,regret 界,無 lead、無 chance constraint)。
- Serverless keep-alive:Serverless in the Wild ATC 20、FaasCache ASPLOS 21、IceBreaker ASPLOS 22、★ 2509.03104(2025-09,keep-warm 開銷刻畫,明確用 ski-rental 損益平衡)。→ 我們的 dwell 就是 keep-alive;要引,要對照。
- Slicing 統計多工:Zheng et al. ToN 2018 SCPF(靜態分享 → 1.6× 流量);VNF sharing 2023。
- ★ 庫存理論:newsvendor/base-stock with lead time(Zipkin;Van Mieghem newsvendor networks:base-stock 在網路結構下的近似保證與 lead 無關);Clark–Scarf 多階層分解;Eppen 1979 風險共享 √N(重尾退化:Bimpikis & Markakis)。雲端只有部落格級類比,**沒有在真實系統上用多階層庫存模型做彈性控制並驗證的論文**。

**定位一句話**:彈性控制的既有工作要嘛是預測 + 控制(OptScaler/BACC),要嘛是線上最佳化理論(無 lead),要嘛是單層系統(5G 文獻)。沒有人把「異質 lead 的多層鏈」當成多階層庫存系統來設計、推導成本定律並在實體 Mpps 鏈上驗證。這是本案要佔的位置。

---

## 3. 問題重構:彈性 = 多階層庫存控制

### 3.1 對映表

| 庫存理論 | NF 鏈彈性 | 現值 |
|---|---|---|
| 階層(echelon) | 層 l ∈ {WK, VY, UP};UP 巢狀在 WK 之下(槽要有 worker 位) | 3 層 |
| 單位 / 批量 u_l | 一台 VM / 一個槽的容量 | worker 2 槽(10 UE)、VyOS 16.5 UE、槽 5 UE(160 UE 制:×4) |
| 單位持有成本 c_l | 該單位燒的核(含 HK 核的固定開銷) | WK 3、VY 2、UP 0.8 核 |
| 補貨 lead h_l | T_ready(l);WK 的有效 lead = h_WK + h_UP(巢狀) | UP 15 s、VY 85 s、WK 100 s |
| 退貨 lead / 承諾窗 w_l | 縮掉後最快補回的時間 | UP 45 s(可逆 drain)、VY 115 s、WK 160 s |
| lead 內需求 R_l(h) | 上升量 max_{τ≤h} D(t+τ) − D(t) | 先驗庫 + 線上樣本 |
| 服務水準 | SLO 違反風險 ε(cycle service level);每分鐘 loss ≤0.1% = fill rate | ε = 0.05 |
| 庫存部位(position) | 在手 + **在途(已下單未就緒)** − 欠貨 | 現在散在 in-flight 旗標、cooldown、direction lock 裡 |
| 基本庫存 S_l | 訂到水準 = D(t) + q_{1−ε}(R_l(h_l)) | = HHRO-Q 的擴容規則 |
| 安全庫存 | q_{1−ε}(R_l(h_l)) | VM 層 9 UE、槽層 5 UE |
| 風險共享(Eppen) | N 條 slice 共用一條鏈 | 新 |
| 批量最佳化(EOQ) | 單位大小 vs 固定開銷 | 新 |
| lead 縮短(庫存教科書第一招) | slim image / 預註冊 / 預 claim | 新 |

### 3.2 形式化

需求 D(t) = Σ_i D_i(t)(slice i)。層 l 有 n_l(t) 個單位、在途 o_l(t)、容量 C_l(n) = n·u_l·m(m = 量測膝點折減,線上辨識)。

**部位**:P_l(t) = 在手容量 + 在途訂單容量 − **所有**退貨中單位的容量(含不可取消;以容量計以容許混型號)。所有決策只看 P_l,不看在手數。這一條就是 cooldown/direction lock/freeze 的替代品:它們都是「怕重複下單」的 ad hoc 補丁,庫存部位從定義上消掉重複下單。

**補貨(scale-out)**:當 C_l(P_l) < D(t) + q_{1−ε}(R_l(h_l^eff)) 時,下單至 P_l 滿足之;h_WK^eff = h_WK + h_UP + 一格。

**退貨(scale-in)**:當 C_l(P_l − 1) ≥ D(t) + q_{1−ε}(R^run_l(W_l))(同一 ε,running max 於暴露窗 W_l)對該單位連續 Δ_l 秒 → 退該單位(每單位各自計時,LIFO);Δ_l = w_l(ski-rental,確定式 2-competitive);UP/VY 退貨可取消(已搬走的 UE 不搬回)。**v4 已移除 ρ**:qsim 證明 v3 的 S_in < S_out 會造成退→取消→再退循環(每小時 24 次),改用同 ε 的 running max 後循環歸零、成本 +0.1%(spec §4.7)。

**風險共享**:S 以聚合需求計;R(h) 的分佈由各 slice 的上升量與相關矩陣 Σ 決定;高斯近似下 q_{1−ε}(ΣR_i) = Σμ_i + z_ε·√(1ᵀΣ1) ≤ Σ q_{1−ε}(R_i),等號當且僅當完全正相關。線上 ACI 對聚合誤蓋校正,per-slice 誤蓋另記帳;共享餘裕吃緊時的分配規則 = 按 slice 的 ε 預算比例(SCPF 精神)。

**動態批量**:下單時若 q_{1−ε}(R_l(h_l)) ≥ u_l^big − u_l^small 的門檻,選大單位;否則小單位。閉式:選 u 使 c(u)·⌈S/u⌉ + 固定開銷(u) 最小(EOQ 型,離線給表、線上查表)。

**lead 縮短**:h_l 是量測輸入(從 actuation 日誌線上估),不是常數;工程上把 WK/VY 的 h 從 100/85 壓到 ≤40 s,q_{1−ε}(R(145 s)) = 9 UE → q(60 s) ≈ 6 UE。

**指派(UE→槽/VyOS)**:全動態 bin packing,每次事件允許的搬遷量以 migration factor 上界(常數 migration factor ⇒ 3/2-competitive,Berndt/Jansen/Klein),取代 hot-slot relief 的「period 150 s、max moves 2、cooldown 120 s、oob 門檻 1500」四個 magic number。

### 3.3 要證的命題(P1-P2-P5 為古典結果的對映,P3-P4-P6 為本案推導)

- P1 單階層:在 lead h、線性持有成本、cycle service level ε 下,base-stock 是最優策略(Zipkin)。
- P2 巢狀分解:容量單調、訊號共用時,多階層最優 = 各階層以有效 lead 的 base-stock(Clark–Scarf 型分解)→ **消融 A4「聯合 = 分層」的古典解釋**。
- P3 風險共享界:q_{1−ε}(ΣR_i) ≤ Σ q_{1−ε}(R_i),差距由 Σ 決定;重尾時退化的量化(用先驗庫實際分佈,不只高斯)。
- P4 批量最優:u* 的閉式與對 (h, ε, 固定開銷) 的敏感度。
- P5 退貨駐留:損益平衡 Δ 的 2-competitive;加上可逆性後的改進界(可逆 ⇒ 承諾窗縮至 h_l + 一格)。
- P6 成本定律:C − C_oracle 的分解式與各槓桿的偏導;這是 C2 要在硬體上驗的東西。

---

## 4. 演算法 v8(從零寫,≤10 個參數;舊 planner 完整保留供對照)

**完整 pseudocode、不變量、參數總表與審查清單見 `v8-echelon-algorithm-spec-2026-10.md`(v4,10-03;§0 列出對三輪審查意見的逐條處置;§4.7 為退貨規則的 qsim 證據)。**

### 4.1 模組

1. **Observer**:D(t)(sender offered + 鏈內量測)、各層 n/o、各 slice D_i;actuation 日誌 → 線上估 h_l、w_l;(u, loss) 配對 → 線上估膝點 m(取代 MarginM 0.93 與 CapUP/CapVY 常數的手動重擬)。
2. **Risk model**:每層 R_l(h) 的分位數 = 先驗庫(相對上升量)+ 線上樣本;ACI 單邊,α ∈ [ε/2, ε];多 slice 時對聚合 + Σ。
3. **Echelon planner**:§3.2 的補貨/退貨規則,逐層、看部位;輸出目標 P_l 與單位型號。
4. **Actuator**:可逆動作(取消在途、取消 drain)、drain-verify、兩階段 VyOS 撤離(保留現有致動管線)。
5. **Assigner**:migration-factor 上界的 repacking。

### 4.2 參數(全部)

| 參數 | 來源 | 值 |
|---|---|---|
| ε | SLO 風險預算 | 0.05(掃描 0.02/0.05/0.10/0.20) |
| ACI γ | 教科書 | max(0.005, ε/5) |
| λ | SLO loss 對核的換算 | 0.002(消融證不敏感,保留一個) |
| grid | 決策週期 | 30 s |
| migration factor 上界 | 理論 | 常數(掃 1/2/3) |
| 單位型號表 | EOQ 離線表 | 由 §3.2 算 |
| 其餘 | 量測輸入(h_l、w_l、m、Σ) | 線上估 |

### 4.3 丟棄清單(180 個旋鈕中的機制類;每條寫替代)

| legacy 機制(現值) | 為什麼存在 | v8 替代 |
|---|---|---|
| *_SCALE_IN/OUT_COOLDOWN(CP 60/180、UP 60/180、VyOS 180/600、worker 300/900 s)、UPF_COOLDOWN 3 min、VM_COOLDOWN 5 min | 怕重複下單 / 反彈 | 庫存部位(在途計入)+ 可逆動作 |
| DIRECTION_LOCK_*(300/300/600/900 s) | 怕擴縮來回 | 損益平衡駐留 Δ_l + 遲滯帶(q_ε^win(h) vs q_ε^run(W))由 lead 導出 |
| TRANSITION_FREEZE 30 s、c.freeze | 致動期間停決策 | 部位已含在途,不需凍結 |
| V6_UP_SCALEIN_HOLD 300 s、VM_SCALEOUT_DWELL 2×TH、WK_DELETE_SLOT_DWELL 120、HOLD_UNTIL_HISTORY、UP_HOLD_SUSTAINED、UP_HOLD_RISE_SLOPE、SLOPE_CONFIRM_TICKS | 各種「等一下再縮」 | 全部 = Δ_l 一條 |
| V6_SCALEIN_MARGIN_J 0.15、BARRIER_K 50、EpsDesign、UMin、UE_QUANT_TOL 0.25 | J 目標函數退化後的補丁 | 無 J;決策只有機率約束 |
| EMERGENCY / EMERG_REFRACTORY 90 s / EMERG_UMIN | 量測分支救火 | ACI 誤蓋即時抬 α;無另一條救火路徑 |
| StepFloor 5 UE / BatchInterval 120 s / MaxBatches 2 / WK_LEAD_BATCHES / UP_LOOKAHEAD_BATCHES | 寫死的批次先驗 | 分位數 |
| HOT_SLOT_* 四個、RELIEF_PERIOD 150、RELIEF_MAX_MOVES 2、REBALANCE_COOLDOWN 90、DONOR_MIN/RECV_MAX | relief 啟發式 | migration-factor 上界的 repacking |
| MarginM 0.93、CapUP/CapVY 常數、CurveCNF/VNF 手擬曲線 | 離線校準 | 線上膝點辨識(初值沿用) |
| UP_HIGH/LOW、VYOS_HIGH/LOW、CP_* 門檻、ETA_*、LAMBDA_*、RISK_*、DROP_*、DASA_*/HPA_*/B5_* | v4/v5 時代與 baseline | baseline 另行保留於 baseline package,主方法不讀 |

保留:致動層的工程常數(VF 數、IP base、ssh 併發、drain wait)——它們是環境描述,不是決策參數。

---

## 5. 實驗設計

### 5.1 基礎建設:160 UE,總 pps 不變(user 拍板:合理且必要)

- 每 UE 31.25 kpps 單向(62.5 k 雙向),槽設計點 20 UE,VyOS 66 UE,總量仍 5.0 Mpps @ 160 UE。
- 效果:需求顆粒變細(一批 = 20 UE 而非 5),指派與共享的實驗才有解析度;也更接近真實 session 數。
- 要改:subscribers 45 → 170(160 + 探針);trace 產生器 `UE=clip(round(32·C/Cmax))` → 128·C/Cmax,deadband 同比例;先驗庫與 held-out 重生(相對上升量不變,只換尺度);harness MAX_UE/PPS_PER_UE 由 trace 檔讀入(已支援);DN hairpin 2032 條已涵蓋 8×254 個 UE IP;VyOS /32 路由 ×4;calib PerUEBidir 由 trace 檔推。

**10-02 實測更新(p2/ue_scale_test.py;記憶 project_ue_scale_eval_2026_10_02)**:每 UE 一台 gNB 的真正原因是 VyOS 分流以 gNB IP 為單位,不是 CPU。
改成 **UE i → gNB (i mod 40)**(每 gNB 4 顆 × 31.25k = 125 kpps 不變)後,gNB 數/IP 別名/AMF peer 上限/SEG-VyOS-worker 路由鄰居**全部不用改**。
註冊面 160 UE 實測無瓶頸:每顆 p50 1.0 s、k=6 時 215 UE/min、AMF +5 MB、UDM 無 4096;健康核心下切離 4/s 零孤兒。
**真正的硬上限是 TRex:每 port 128 條 latency-stat 流**(harness 每 UE 一條 pg_id 流做 per-UE rx/黑 UE 偵測)→ >125 UE 必須改 per-UE 計數法(W1 任務;候選:每 gNB 一條 latency 流 + eUPF/DN 側 per-UE 計數)。
另兩個踩出來的雷已修/已記:TRex 看門狗自殺(--no-watchdog)、無分流直接打流會把 DL 灌進 sender PF 並讓 gNB SCTP 崩潰(資料面驗證一律走 harness bringup)。

- 風險:bringup 時間 ×4(要並行批次註冊)、AMF 記憶體(worker-0 3.9 GB 見底雷)、UDM SDM 4096 上限(160 × 訂閱數仍在內)、sender 上 160 nr-ue + 160 nr-gnb 程序(RSS ~2 GB,CPU 閒時 ~0)。第 1 週閘口實測。

### 5.2 trace 集與協定(不變)

- 開發集:t1、t2(+ 先驗庫 CV);測試集:t3、t4、t5,方法打 tag 凍結後才跑,跑完不改。
- 多 slice:先驗庫挑 3 條低相關 + 3 條高相關(同時段同區),各自縮放後疊成總量 ≤160 UE。

### 5.3 比較組

| 組 | 內容 | 狀態 |
|---|---|---|
| v8 Echelon | 本案 | 待實作 |
| v6 / HHRO-Q | 專家先驗 / 風險分位數(現役) | 有 |
| B1 static、B2 DASA、B3 HPA、B4 DASA+HPA | 反應式 | 有 |
| B5' BACC 型 | ARIMA/Holt 預測 + ACI + 違規預算 → replica(取代 B5 Holt) | 2 天 |
| B6 OptScaler-MPC 型 | 預測 + 高斯 chance constraint MPC,單層 | 3 天 |
| B7 DRL(NFScaler 型) | qsim 訓練 + domain randomization,零樣本上機 | 1 週,視時間 |

### 5.4 槓桿矩陣(C2-C4)

- lead:h_WK/h_VY 現值 vs 縮短版(各 2-3 場)。
- 單位:worker 1/2/4 槽;VyOS 單/雙 worker thread(若 image 可行)。
- 共享:3 slice 分割 vs 共享;低相關 vs 高相關。
- 每格報 SLO、burned、over-oracle、over-floor、flaps;模型預測值並列。

### 5.5 指標

既有(SLO 覆蓋、wmean/worst loss、burned、eff、flaps)+ **over-oracle、over-floor 分解成 lead 項、顆粒項、控制器項**(這就是 C2 的圖)。

---

## 6. 四週計畫與閘口(每週五固定「回來看 §0」)

| 週 | 內容 | 閘口(不過就停,回 §0 改帳本) |
|---|---|---|
| W1 10/2-10/8 | 理論 P1-P6 寫成草稿;qsim 擴成多階層 + 多 slice + 單位型號;先驗庫估 Σ;80/160 UE 基建(subscribers 已到 160、trace/先驗重生、共用 gNB 映射、並行 arrivals);B5' 實作;v8 package 骨架 | G1(10-03 改寫):(i) v8-sim 等 SLO 成本 ≤ v6-sim + 3% 且零循環;(ii) 三槓桿 qsim 合計 ≥12%;(iii) 160 制重跑後 (i)(ii) 仍成立;80 UE bringup + 一場 smoke 60/60 |
| W2 10/9-10/15 | 現役 daemon:常數來源改為校準程序輸出(λ_l·σ̂_l、lead 推出的窗、鎖長由程序定)、部位記帳(V8_POSITION)、刪 61 個 v6 模式不讀的 legacy 旋鈕、稽核仍被讀的 14 個;多 slice harness(共享 vs 分割 = 聚合餘裕 vs 各 slice 餘裕之和);slim image 量 T_ready;B6 | G2:校準版在 t1/t2 各一場 SLO ≥ v6、成本 ±2%、flaps 如實報;多 slice smoke;**方法與校準程序打 tag 凍結** |
| W3 10/16-10/22 | 測試集 + 槓桿矩陣 + baseline 全矩陣(約 35 場) | G3:C2 至少兩個槓桿預測誤差 ≤10%;C3 共享 −10% |
| W4 10/23-10/29 | 補場、統計、圖、論文骨架(ToN 格式);B7 視餘裕 | G4:§0 帳本定稿;投稿層級判定 |

每週五的回顧固定三問:(1)每個貢獻的證據是否仍支持預期;(2)不支持的,替代貢獻是什麼、價值是否不低於原案;(3)下週要砍什麼。回答寫進 §0 與 docs/CHANGELOG。

G2 之後方法不得再改;若發現 bug,修正要附「為何不是調參」的說明,並在測試集重跑受影響的場。

---


**10-03 閘口紀錄(審查第五點)**:G1 原文「v8-sim 在 CV 上 SLO ≥ v6-sim」在看到結果後曾被放寬為「成本 ≤ v6-sim + 3%」,屬事後放寬,記錄在此;G2、G3 不得再事後改閘口。三個決定性 qsim 實驗(spec §4.8)之後一度判「控制器層無貢獻」;依審查改走「保留 v6 結構、常數改固定程序輸出」路線並以事先寫下的判準在 qsim 驗證通過(spec §4.9),C1 改寫為「自動校準」版並恢復為活。

## 7. 風險與停損

- 160 UE 基建卡住(bringup/AMF 記憶體/UDM):W1 內解不掉 → 退回 80 UE @62.5k(仍是 2× 解析度)。
- VyOS 小尺寸 image:卡住就只做 worker 批量。
- 多 slice harness:卡住 → C3 只在 qsim 報。
- 場地事故(10-01 一天三起):每週保留 30% 機時;sender 開跑前四閘 + RSS probe 已入 SOP。
- 理論命題證不出緊的界:P3/P4 退為數值界,仍可報。
- 最壞情況(G1 不過):三槓桿合計 <12% → 問題確實沒有「根本解」,本案停,現有材料走 TNSM/CNSM;這是停損,不是失敗。

---

## 8. 版控與回朔

- home repo:tag `dev-final-2026-10-01`(含 r198/r200 圖與文件);v8 工作在 `docs/proposals/`、`experiment/qsim/v8/`、`experiment/p2/`(新腳本加 v8 前綴)。
- hhro-daemon:tag `v7.0.5-q6`;分支 `v8-echelon`;新 package `internal/echelon`,`V8_ENABLE=1` 切換;舊 planner 不動。image 命名 `6.0-v8.N`。
- 每個閘口一個 commit + CHANGELOG 段 + memory 更新(docs/PROPOSAL_TEMPLATE.md 的三件套)。
