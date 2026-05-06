from statistics import mean

from matplotlib import gridspec
import matplotlib.animation as animation
import matplotlib.pyplot as plt
from matplotlib.ticker import FormatStrFormatter, FuncFormatter
import randomcolor
import colorsys
from typing import List, Tuple

from .utils import format_bps


def distinct_colors(n: int) -> List[str]:
    """
    Tạo ra n màu khác biệt rõ ràng ở định dạng hex.
    """
    hues = [i / n for i in range(n)]
    colors = [colorsys.hsv_to_rgb(h, 0.7, 0.9) for h in hues]
    return ["#%02x%02x%02x" % (int(r*255), int(g*255), int(b*255)) for r, g, b in colors]


class Graph:
    def __init__(self, base_stations, clients, xlim: Tuple[int, int], map_limits: Tuple[Tuple[int, int], Tuple[int, int]],
                 output_dpi: int = 500, scatter_size: int = 15, output_filename: str = 'output.png'):
        """
        Khởi tạo đối tượng Graph dùng để trực quan hóa.
        """
        self.output_filename = output_filename
        self.base_stations = base_stations
        self.clients = clients
        self.xlim = xlim
        self.map_limits = map_limits
        self.output_dpi = output_dpi
        self.scatter_size = scatter_size
        self.fig = plt.figure(figsize=(16, 12))
        # Backend Matplotlib mới không còn luôn expose set_window_title trên canvas.
        canvas_manager = getattr(self.fig.canvas, 'manager', None)
        if canvas_manager is not None and hasattr(canvas_manager, 'set_window_title'):
            canvas_manager.set_window_title('Network Slicing Simulation')
        elif hasattr(self.fig.canvas, 'set_window_title'):
            self.fig.canvas.set_window_title('Network Slicing Simulation')

        self.gs = gridspec.GridSpec(6, 3, width_ratios=[6, 3, 3])

        # Dùng màu riêng biệt cho từng base station.
        colors = distinct_colors(len(base_stations))
        for c, bs in zip(colors, self.base_stations):
            bs.color = c

        self.slice_names = [network_slice.name for network_slice in self.base_stations[0].slices] if self.base_stations else []
        self.slice_colors = {
            slice_name: color for slice_name, color in zip(self.slice_names, distinct_colors(max(len(self.slice_names), 1)))
        }

    def draw_live(self, *stats):
        """
        Vẽ animation trực tiếp của mô phỏng.
        """
        ani = animation.FuncAnimation(self.fig, self.draw_all, fargs=stats, interval=1000)
        plt.show()

    def draw_all(self, *stats):
        """
        Vẽ toàn bộ biểu đồ của mô phỏng.
        """
        plt.clf()
        self.draw_map()
        self.draw_stats(*stats)

    def draw_map(self):
        """
        Vẽ bản đồ gồm base station và client.
        """
        markers = ['o', 's', 'p', 'P', '*', 'H', 'X', 'D', 'v', '^', '<', '>', '1', '2', '3', '4']
        self.ax = plt.subplot(self.gs[:, 0])
        xlims, ylims = self.map_limits
        self.ax.set_xlim(xlims)
        self.ax.set_ylim(ylims)
        self.ax.yaxis.set_major_formatter(FormatStrFormatter('%.0f m'))
        self.ax.xaxis.set_major_formatter(FormatStrFormatter('%.0f m'))
        self.ax.set_aspect('equal')
        
        # Vẽ base station.
        for bs in self.base_stations:
            circle = plt.Circle(bs.coverage.center, bs.coverage.radius,
                                fill=False, linewidth=2, alpha=0.9, color=bs.color)
            self.ax.add_artist(circle)
        
        # Vẽ client.
        legend_indexed = []
        for c in self.clients:
            label = None
            if c.subscribed_slice_index not in legend_indexed and c.base_station is not None:
                label = c.get_slice().name
                legend_indexed.append(c.subscribed_slice_index)
            self.ax.scatter(c.x, c.y,
                            color=c.base_station.color if c.base_station is not None else '0.8',
                            label=label, s=15,
                            marker=markers[c.subscribed_slice_index % len(markers)])

        box = self.ax.get_position()
        self.ax.set_position([box.x0 - box.width * 0.05, box.y0 + box.height * 0.1, box.width, box.height * 0.9])

        leg = self.ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.05),
                             shadow=True, ncol=5)

        legend_handles = getattr(leg, "legendHandles", None)
        if legend_handles is None:
            legend_handles = getattr(leg, "legend_handles", [])
        for i in range(min(len(legend_indexed), len(legend_handles))):
            legend_handles[i].set_color('k')

    def draw_stats(
        self,
        vals,
        vals1,
        vals2,
        vals3,
        vals4,
        vals5,
        vals6,
        vals7,
        vals8,
        vals9,
        slice_completion_latency_stats=None,
        slice_first_service_latency_stats=None,
    ):
        """
        Vẽ các biểu đồ thống kê.
        """
        self.ax1 = plt.subplot(self.gs[0, 1])
        self.ax1.plot(vals)
        self.ax1.set_xlim(self.xlim)
        locs = self.ax1.get_xticks()
        locs[0] = self.xlim[0]
        locs[-1] = self.xlim[1]
        self.ax1.set_xticks(locs)
        self.ax1.use_sticky_edges = False
        self.ax1.set_title(f'Connected Clients Ratio')

        self.ax2 = plt.subplot(self.gs[1, 1])
        self.ax2.plot(vals1)
        self.ax2.set_xlim(self.xlim)
        self.ax2.set_xticks(locs)
        self.ax2.yaxis.set_major_formatter(FuncFormatter(format_bps))
        self.ax2.use_sticky_edges = False
        self.ax2.set_title('Total Bandwidth Usage')

        self.ax3 = plt.subplot(self.gs[2, 1])
        self.ax3.plot(vals2)
        self.ax3.set_xlim(self.xlim)
        self.ax3.set_xticks(locs)
        self.ax3.use_sticky_edges = False
        self.ax3.set_title('Bandwidth Usage Ratio in Slices (Averaged)')

        self.ax4 = plt.subplot(self.gs[3, 1])
        self.ax4.plot(vals7)
        self.ax4.set_xlim(self.xlim)
        self.ax4.set_xticks(locs)
        self.ax4.yaxis.set_major_formatter(FormatStrFormatter('%.2f ms'))
        self.ax4.use_sticky_edges = False
        self.ax4.set_title('Average Completion Latency')

        self.ax4b = plt.subplot(self.gs[4, 1])
        self.ax4b.plot(vals3)
        self.ax4b.set_xlim(self.xlim)
        self.ax4b.set_xticks(locs)
        self.ax4b.use_sticky_edges = False
        self.ax4b.set_title('Client Count Ratio per Slice')

        self.ax4c = plt.subplot(self.gs[5, 1])
        has_completion_slice_latency = bool(slice_completion_latency_stats)
        if has_completion_slice_latency:
            plotted = False
            for slice_name, values in slice_completion_latency_stats.items():
                if any(value > 0 for value in values):
                    self.ax4c.plot(values, label=slice_name, color=self.slice_colors.get(slice_name))
                    plotted = True
            if plotted:
                self.ax4c.legend(fontsize=8, loc="upper left")
            else:
                self.ax4c.text(0.5, 0.5, "No completion slice latency yet", ha="center", va="center")
            self.ax4c.set_xlim(self.xlim)
            self.ax4c.set_xticks(locs)
            self.ax4c.yaxis.set_major_formatter(FormatStrFormatter('%.2f ms'))
            self.ax4c.use_sticky_edges = False
            self.ax4c.set_title('Average Completion Latency per Slice')
        else:
            self.ax4c.axis('off')
            self.ax4c.text(0.5, 0.5, "No completion slice latency data", ha="center", va="center")

        self.ax5 = plt.subplot(self.gs[0, 2])
        self.ax5.plot(vals4)
        self.ax5.set_xlim(self.xlim)
        self.ax5.set_xticks(locs)
        self.ax5.use_sticky_edges = False
        self.ax5.set_title('Coverage Ratio')

        self.ax6 = plt.subplot(self.gs[1, 2])
        self.ax6.plot(vals5)
        self.ax6.set_xlim(self.xlim)
        self.ax6.set_xticks(locs)
        self.ax6.yaxis.set_major_formatter(FormatStrFormatter('%.3f'))
        self.ax6.use_sticky_edges = False
        self.ax6.set_title('Block ratio')

        self.ax7 = plt.subplot(self.gs[2, 2])
        self.ax7.plot(vals6)
        self.ax7.set_xlim(self.xlim)
        self.ax7.set_xticks(locs)
        self.ax7.yaxis.set_major_formatter(FormatStrFormatter('%.3f'))
        self.ax7.use_sticky_edges = False
        self.ax7.set_title('Handover ratio')

        self.ax8 = plt.subplot(self.gs[3, 2])
        has_first_service_slice_latency = bool(slice_first_service_latency_stats)
        if has_first_service_slice_latency:
            plotted = False
            for slice_name, values in slice_first_service_latency_stats.items():
                if any(value > 0 for value in values):
                    self.ax8.plot(values, label=slice_name, color=self.slice_colors.get(slice_name))
                    plotted = True
            if plotted:
                self.ax8.legend(fontsize=8, loc="upper left")
            else:
                self.ax8.text(0.5, 0.5, "No first-service slice latency yet", ha="center", va="center")
            self.ax8.set_xlim(self.xlim)
            self.ax8.set_xticks(locs)
            self.ax8.yaxis.set_major_formatter(FormatStrFormatter('%.2f ms'))
            self.ax8.use_sticky_edges = False
            self.ax8.set_title('Average First-Service Latency per Slice')
        else:
            self.ax8.axis('off')
            self.ax8.text(0.5, 0.5, "No per-slice latency data", ha="center", va="center")

        self.ax9 = plt.subplot(self.gs[4:, 2])
        row_labels = [
            'Initial number of clients',
            'Average connected clients',
            'Average clients per slice',
            'Average bandwidth usage',
            'Average load factor of slices',
            'Average coverage ratio',
            'Average block ratio',
            'Average handover ratio',
            'Average completion latency',
            'P95 latency',
            'Latency violation ratio',
        ]
        l, r = self.xlim
        cell_text = [
            [f'{len(self.clients)}'],
            [f'{mean(vals[l:r]):.2f}'],
            [f'{mean(vals3[l:r]):.2f}'],
            [f'{format_bps(mean(vals1[l:r]), return_float=True)}'],
            [f'{mean(vals2[l:r]):.2f}'],
            [f'{mean(vals4[l:r]):.2f}'],
            [f'{mean(vals5[l:r]):.4f}'],
            [f'{mean(vals6[l:r]):.4f}'],
            [f'{mean(vals7[l:r]):.2f} ms'],
            [f'{mean(vals8[l:r]):.2f} ms'],
            [f'{mean(vals9[l:r]):.4f}'],
        ]
        
        self.ax9.axis('off')
        self.ax9.axis('tight')
        self.ax9.tick_params(axis='x', which='major', pad=15)
        self.ax9.table(cellText=cell_text, rowLabels=row_labels, colWidths=[0.35, 0.2], loc='center right')

        plt.tight_layout()

    def save_fig(self):
        """
        Lưu hình hiện tại ra file.
        """
        self.fig.savefig(self.output_filename, dpi=self.output_dpi)

    def show_plot(self):
        """
        Hiển thị cửa sổ biểu đồ.
        """
        plt.show()

    def get_map_limits(self):
        """
        Hàm cũ: lấy giới hạn bản đồ dựa trên vùng phủ của base station.
        """
        x_min = min([bs.coverage.center[0]-bs.coverage.radius for bs in self.base_stations])
        x_max = max([bs.coverage.center[0]+bs.coverage.radius for bs in self.base_stations])
        y_min = min([bs.coverage.center[1]-bs.coverage.radius for bs in self.base_stations])
        y_max = max([bs.coverage.center[1]+bs.coverage.radius for bs in self.base_stations])

        return (x_min, x_max), (y_min, y_max)
