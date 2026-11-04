階段：P0
判定：PASS（10-26 更新；機時帳放不下 → 48 場全基線承諾已停，P5 協定待 user 決定）
修改 commit / 檔案與 SHA：新檔 qsim/s7r/{repo_map.json, protocol.json, splits.py, out/P0/*}（out/P0/sha256.json）；daemon worktree /home/user/hhro-daemon-s7r（branch s7r @1bd509b，無修改）；原 /home/user/hhro-daemon 未動（狀態存 out/P0/daemon_git_status.txt）
執行命令與開始/結束時間：2026-10-26 06:3x–07:xx；python3 qsim/s7r/splits.py；t8 重現（out/P0/reproduce_t8.txt）；sha256sum（out/P0/frozen_sha256.txt）
測試：splits 6/6 fold 全過；t8 登記預測 8/8 逐值重現；Go 等價 harness：user 提供 go1.26.4 後於 worktree 執行，48 情境 EQUIV GATE PASS（out/P0/go_equiv_compare.txt）
指標：機時帳（out/P0/budget.json）：近 20 場 p50 106.8 / p90 112.0 min；48 正式 + 4 pilot + 7 預留 + 4 探針 = 106.1 h（均值）/ 111.1 h（p90）；P5 窗 96 h → 放不下
機制標籤：無（P0 不涉方法效果）
失敗或未覆蓋處：
 1. Go 工具鏈不可用（sudo docker 被權限擋）→ Go 等價測試、P2 Go evaluator、P4 daemon 全卡
 2. 機時帳超出：照 §12 停止全基線 campaign 的承諾，等 user 決定（例如事前縮為 36 場的不同協定）
 3. per-UE 搬遷日誌未逐場存檔（/tmp/rehome_agent.log 無日期）→ P1 的 assignment 比對改用 prom upf_sessions（15 s、逐槽），解析度照實標
 4. B2+E / B3+E 無 manifest、無對等測試（P4 §7.2 要補）
 5. 密封池 2026-10-26..27 資料尚未完整（10-27 約 15:15Z 後才完整）→ 資料品質檢查延到該時
下一階段是否允許：是（P1–P3 為離線工作；P5 場次協定待 user 決定）
剩餘實機時數與既定場次能否容納：不能（見上）
獨立審查結果與原始重算附件：尚未獨立複核
