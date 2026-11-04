階段：P1
判定：FAIL
修改 commit / 檔案與 SHA：b9a3065（event_phys / objective / scenario_bank / tests）、228396c（replay 分組登記）、f604717（profiling 常數更新 + 延後注入）；sha 見 out/P1/sha256.json
執行命令與開始/結束時間：python3 qsim/s7r/tests/test_p1.py；python3 qsim/s7r/replay.py causal（23 場，2026-10-26）
測試：單元測試 15 passed / 0 failed / 0 skipped（T10 的決策部分屬 P2）
指標（causal replay，23 場模型驗證 run）：
 - fleet/placement episode 召回 7/12 = 58.3%（門檻 ≥80%）→ 不過；支持度 12 個 episode / 10 場（≥5 / ≥3）→ 足
 - 乾淨分鐘誤報 17/1340 = 1.3%（≤5%）→ 過
 - 成本 MAPE 1.04%（≤3%）→ 過
機制標籤：[已驗證於模擬] 漏掉的 t8 第 20–22 分鐘：硬體 30 UE、每槽 5 顆時 p99 2.9 ms / loss 2.29%，模型在 5-UE 膝點上判不溢位；r495 的兩段來自 r34b 過期 drain 公告（harness 輸入缺陷），模型用 r34c 語義不會重現
失敗或未覆蓋處：observed-event replay 未跑（已有登記門檻不過，依協定停止）；降膝點（R38 型）依協定排除，不以擬合補回
揭露：worker 就緒 90→51 s 與 relief 時點是看到 r504 試跑後才改（數值只取自 profiling run r500/r502/r505），全量重播前已 commit
下一階段是否允許：否（模型不過不進校準）
剩餘實機時數與既定場次能否容納：不適用（不上機）
獨立審查結果與原始重算附件：out/P1/independent_review.md（完成：數字、逐場清單、episode 全部一致；召回不過確認）。審查指出 r471/r478 起始 worker 數取第 0 分鐘末計數、多算開場 31/39 s 才建的 worker；更正為 2 台後重跑，第 20 分鐘仍判不違規 → 判定不變。
