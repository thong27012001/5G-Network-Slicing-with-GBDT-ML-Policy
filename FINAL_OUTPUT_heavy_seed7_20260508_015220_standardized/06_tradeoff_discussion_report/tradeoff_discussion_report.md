# Trade-off Discussion Report

## Nhận xét nhanh

ML tăng throughput tổng. ML cải thiện completion ratio của eMBB. ML giảm completion latency của URLLC. Đánh đổi: p95 latency tăng, cần phân tích thêm tail latency.

## Bảng chỉ số chính

| Chỉ số | Giá trị |
|---|---:|
| Total bandwidth delta | `6.22%` |
| Block ratio delta | `0.0000` |
| Connected clients delta | `-0.0007` |
| Average latency delta | `0.88%` |
| p95 latency delta | `2.12%` |
| State SLA share baseline -> ML | `0.0010 -> 0.0010` |
| eMBB completion delta | `0.0077` |
| URLLC completion latency delta | `-0.0057 ms` |

## Guardrail

- Guardrail report: `N/A`
