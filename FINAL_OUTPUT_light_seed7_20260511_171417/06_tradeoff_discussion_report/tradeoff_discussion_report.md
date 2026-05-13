# Trade-off Discussion Report

## Nhận xét nhanh

ML tăng throughput tổng. ML cải thiện completion ratio của eMBB. ML giảm completion latency của URLLC. Đánh đổi: p95 latency tăng, cần phân tích thêm tail latency.

## Bảng chỉ số chính

| Chỉ số | Giá trị |
|---|---:|
| Total bandwidth delta | `7.21%` |
| Block ratio delta | `0.0000` |
| Connected clients delta | `-0.0004` |
| Average latency delta | `-0.13%` |
| p95 latency delta | `16.99%` |
| State SLA share baseline -> ML | `0.0070 -> 0.0060` |
| eMBB completion delta | `0.0035` |
| URLLC completion latency delta | `-0.0047 ms` |

## Guardrail

- Guardrail report: `N/A`
