# Trade-off Discussion Report

## Nhận xét nhanh

ML tăng throughput tổng. ML cải thiện completion ratio của eMBB. ML giảm completion latency của URLLC. Đánh đổi: p95 latency tăng, cần phân tích thêm tail latency. Đánh đổi: state-level SLA violation share tăng.

## Bảng chỉ số chính

| Chỉ số | Giá trị |
|---|---:|
| Total bandwidth delta | `9.08%` |
| Block ratio delta | `0.0000` |
| Connected clients delta | `-0.0025` |
| Average latency delta | `-0.28%` |
| p95 latency delta | `10.13%` |
| State SLA share baseline -> ML | `0.0085 -> 0.0090` |
| eMBB completion delta | `0.0089` |
| URLLC completion latency delta | `-0.0042 ms` |

## Guardrail

- Guardrail report: `N/A`
