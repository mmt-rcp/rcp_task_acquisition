import numpy as np
import wx
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.lines import Line2D

from rcp_task_acquisition.utils.constants import COLORS, DEFAULTS, LINE_STYLES, PLOT_CONSTANTS
from rcp_task_acquisition.utils.logger import get_logger

logger = get_logger(__name__)


class GraphPanel(wx.Panel):
    """
    Class for settiing up and displaying the gui graph

    """

    hardware_panel: wx.Panel
    labjack_stream_button: wx.ToggleButton
    contrast_test: wx.ToggleButton
    focus_test: wx.ToggleButton

    def __init__(self, parent, gui_size) -> None:
        super().__init__(parent, -1, style=wx.SUNKEN_BORDER)

        # most of these are placeholders since we will not know which hardware
        # will be used until the task is selected
        self.legend_lines: list[Line2D] = []
        self.legend_labels: list[str] = []
        self.test_legend_lines: list[Line2D] = []
        self.test_legend_labels: list[str] = []
        self.hardware: list[str] = []
        self.constants: list[
            Line2D
        ] = []  # looks to be this, result of (plot,) = self.axes.plot(..)
        self.lines: list[Line2D] = []  # same
        self.labjack_choices: list[wx.Choice] = []
        # self.input_checkboxes = []  # unused
        self.constant_labels: list[str] = []
        self.test_lines: list[Line2D] = []
        self.default_index: list[int] = []
        self.voltage: list[tuple[float, float]] = []
        self.test_focus: Line2D | None = None
        self.color_index = 0
        self.hardware_indices: list[int] = [-1] * 3
        self.white_space = 5
        self.button_width = 150
        self.constants_step = 2
        if gui_size[0] > gui_size[1]:
            ctrlsizer = wx.BoxSizer(wx.HORIZONTAL)
        else:
            ctrlsizer = wx.BoxSizer(wx.VERTICAL)
        self.figure = Figure(figsize=(4, 4))
        # self.figure.patch.set_facecolor((0.09, 0.09, 0.09))

        self.figure.patch.set_facecolor((0.8, 0.8, 0.8))
        canvas = FigureCanvas(self, -1, self.figure)
        ctrlsizer.Add(canvas, 1, wx.ALL)
        # lj_panel = self.create_labjack_panel(self)
        lj_panel = self.add_panels(self)
        ctrlsizer.Add(lj_panel, 0, wx.ALL)
        lj_panel.SetMinSize((-1, 550))
        white_color = (0.09, 0.09, 0.09)  # (0.9,0.9,0.9)
        # creating own x axis with a line/text so there is more control
        setup_axes = self.figure.add_subplot(1, 1, 1)
        setup_axes.set_position((0.01, 0.25, 0.98, 0.7))
        (_plot,) = setup_axes.plot(
            [0, 0, 40000, 40000, np.nan, 40000, 80000, 80000],
            [-2.25, -2, -2, -2.25, np.nan, -2, -2, -2.25],
            color=white_color,
            lw=1,
        )
        setup_axes.text(0, -4, "0", ha="center", color=white_color)
        setup_axes.text(40000, -4, "1", ha="center", color=white_color)
        setup_axes.text(80000, -4, "2", ha="center", color=white_color)
        setup_axes.text(40000, -6, "Seconds", ha="center", color=white_color)
        setup_axes.set_ylim([-10, 15])
        setup_axes.set_frame_on(False)
        setup_axes.invert_xaxis()

        setup_axes.yaxis.set_visible(False)
        self.axes = setup_axes

        self.SetSizer(ctrlsizer)
        ctrlsizer.Fit(self)
        self.Layout()

    def update_graph(
        self,
        hardware: tuple[
            tuple[str, ...],  # hardware list
            tuple[str, ...],  # labjack list
            tuple[str, ...],  # min max
            tuple[tuple[float, float], ...],  # voltage range
        ],
    ) -> None:
        """
        where the actual set up is occurring

        """
        self.hardware = list(hardware[0])
        # self.min_max = list(hardware[2])  # unused
        self.voltage = list(hardware[3])
        options = self.hardware
        options.insert(0, " ")
        self.default_index = []
        for item in DEFAULTS:
            try:
                item_idx = options.index(item)
            except ValueError:
                pass
            else:
                self.default_index.append(item_idx)
        for choice in self.labjack_choices:
            choice.SetItems(options)
        count = 0
        for index in self.default_index:
            self.labjack_choices[count].SetSelection(index)
            count += 1

    def create_labjack_panel(self, panel: wx.Panel) -> wx.StaticBoxSizer:
        # panel = wx.Panel(panel, -1,style=wx.BORDER_NONE)
        box = wx.StaticBox(panel, label="Labjack Graphing")
        box_sizer = wx.StaticBoxSizer(box, wx.HORIZONTAL)
        labjack_sizer = wx.GridBagSizer(3, 2)
        options = self.hardware

        options.insert(0, " ")
        self.labjack_stream_button = wx.ToggleButton(
            box, id=wx.ID_ANY, label="Stream Labjack", size=(self.button_width, -1)
        )
        labjack_sizer.Add(
            self.labjack_stream_button,
            pos=(0, 0),
            span=(0, 2),
            flag=wx.ALL,
            border=self.white_space,
        )

        labjack_choice = wx.Choice(box, id=wx.ID_ANY, choices=options, size=(self.button_width, -1))
        self.labjack_choices.append(labjack_choice)
        labjack_sizer.Add(
            labjack_choice, pos=(1, 0), span=(0, 2), flag=wx.ALL, border=self.white_space
        )

        labjack_choice = wx.Choice(box, id=wx.ID_ANY, choices=options, size=(self.button_width, -1))
        self.labjack_choices.append(labjack_choice)
        labjack_sizer.Add(
            labjack_choice, pos=(2, 0), span=(0, 2), flag=wx.ALL, border=self.white_space
        )

        labjack_choice = wx.Choice(box, id=wx.ID_ANY, choices=options, size=(self.button_width, -1))
        self.labjack_choices.append(labjack_choice)
        labjack_sizer.Add(
            labjack_choice, pos=(3, 0), span=(0, 2), flag=wx.ALL, border=self.white_space
        )

        box_sizer.Add(labjack_sizer, 1, wx.EXPAND | wx.ALL, 3)

        return box_sizer

    def create_hardware_test_panel(self, parent: wx.Panel) -> wx.Panel:
        panel = wx.Panel(parent, -1, style=wx.BORDER_NONE)
        button_width = 150

        box = wx.StaticBox(panel, label="Camera Tests")
        cam_sizer = wx.GridBagSizer(1, 2)

        self.contrast_test = wx.ToggleButton(
            box, id=wx.ID_ANY, label="Test Contrast", size=(button_width, -1)
        )
        self.focus_test = wx.ToggleButton(
            box, id=wx.ID_ANY, label="Test Focus", size=(button_width, -1)
        )

        cam_sizer.Add(
            self.contrast_test, pos=(0, 0), span=(0, 2), flag=wx.ALL, border=self.white_space
        )
        cam_sizer.Add(
            self.focus_test, pos=(1, 0), span=(0, 2), flag=wx.ALL, border=self.white_space
        )

        box_sizer = wx.StaticBoxSizer(box, wx.HORIZONTAL)
        box_sizer.Add(cam_sizer, 1, wx.EXPAND | wx.ALL, 3)
        panel.SetSizer(box_sizer)
        panel.Fit()
        return panel

    def add_panels(self, parent: wx.Panel) -> wx.Panel:
        panel = wx.Panel(parent, -1, style=wx.BORDER_NONE)
        box_sizer = wx.BoxSizer(wx.VERTICAL)

        lj_panel = self.create_labjack_panel(panel)
        self.hardware_panel = self.create_hardware_test_panel(panel)

        box_sizer.Add(lj_panel, 0, wx.ALL)
        box_sizer.Add(self.hardware_panel, 0, wx.RESERVE_SPACE_EVEN_IF_HIDDEN | wx.ALL)
        self.hardware_panel.Hide()
        panel.SetSizer(box_sizer)
        panel.Fit()
        return panel

    def get_hardware_handles(self):
        return self.contrast_test, self.focus_test, self.hardware_panel

    def plot_constants(self, arr_size: int) -> None:

        y_coords = list(np.array([np.nan] * arr_size))
        x_coords = list(np.arange(0, arr_size))
        line_weight = 1
        for index, _ in enumerate(PLOT_CONSTANTS):
            (plot,) = self.axes.plot(
                x_coords,
                y_coords,
                label=PLOT_CONSTANTS[index],
                color=COLORS[self.color_index],
                linestyle=LINE_STYLES[index],
                lw=line_weight,
            )
            self.legend_lines.append(
                Line2D(
                    [],
                    [],
                    color=COLORS[self.color_index],
                    linestyle=LINE_STYLES[index],
                    lw=line_weight,
                )
            )
            self.test_legend_lines.append(
                Line2D(
                    [],
                    [],
                    color=COLORS[self.color_index],
                    linestyle=LINE_STYLES[index],
                    lw=line_weight,
                )
            )
            self.test_legend_labels.append(PLOT_CONSTANTS[index])
            self.legend_labels.append(PLOT_CONSTANTS[index])
            self.color_index += 1
            # line_weight+=0.5
            self.constants.append(plot)

    def update_constants(self, y_points, index: int, lj_value: int) -> None:
        # calculating a new scale for the constants so that they will show up
        # on the top half of the graph, and then plotting them
        # min_new = 15-(index * self.constants_step)
        # max_new = 15-(index * self.constants_step + self.constants_step)
        # min_old = float(self.voltage[lj_value][0])
        # max_old = float(self.voltage[lj_value][1])
        max_new = 15 - (index * self.constants_step)
        min_new = 15 - (index * self.constants_step + self.constants_step)
        min_old = float(self.voltage[lj_value][0])
        max_old = float(self.voltage[lj_value][1])
        y_points = np.array(y_points)
        y_points = (((y_points - min_old) * (max_new - min_new)) / (max_old - min_old)) + min_new

        self.constants[index].set_ydata(y_points)

    def get_graph_button(self) -> wx.ToggleButton:
        return self.labjack_stream_button

    def get_graph_choices(self) -> list[wx.Choice]:
        return self.labjack_choices

    def set_visible(self, index: int, is_visible: bool = True) -> None:
        self.lines[index].set_visible(is_visible)

    def set_visible_const(self, index: int, is_visible: bool = True) -> None:
        self.constants[index].set_visible(is_visible)

    def update_yaxis(self, y_points, index: int, lj_value: int) -> None:
        if index != -1 and lj_value != -1:
            min_old = float(self.voltage[lj_value][0])
            max_old = float(self.voltage[lj_value][1])
            min_new = -1
            max_new = 7
            y_points = np.array(y_points)
            y_points = (
                ((y_points - min_old) * (max_new - min_new)) / (max_old - min_old)
            ) + min_new
            self.lines[index].set_ydata(y_points)

    def create_plot(self, arr_size: int) -> None:
        self.lines = []
        self.x_size = arr_size
        y_coords = list(np.array([np.nan] * arr_size))
        x_coords = list(np.arange(0, arr_size))

        self.plot_constants(arr_size)
        for index, lj_input in enumerate(self.hardware_indices):
            (plot,) = self.axes.plot(x_coords, y_coords, color=COLORS[self.color_index], lw=1)
            self.legend_lines.append(Line2D([], [], color=COLORS[self.color_index], lw=1))
            self.legend_labels.append("")
            self.lines.append(plot)
            self.color_index += 1
        # self.axes.legend(loc="upper left", fontsize=8, labelcolor=(0.9,0.9,0.9),
        # edgecolor=(0.9,0.9,0.9), facecolor=(0.1, 0.1, 0.1))
        for constant in self.constants:
            constant.set_visible(False)
        self.axes.legend(
            self.legend_lines,
            self.legend_labels,
            loc="upper right",
            fontsize=8,
            labelcolor=(0.9, 0.9, 0.9),
            edgecolor=(0.9, 0.9, 0.9),
            facecolor=(0.1, 0.1, 0.1),
            bbox_to_anchor=(-0.01, -0.01, 1.09, 1.09),
        )

    def draw(self) -> None:
        self.figure.canvas.draw()

    def hardware_test(self, arr_size: int, cam_num, cam_names) -> None:
        for plot in self.lines:
            plot.set_visible(False)

        self.test_legend_labels = self.test_legend_labels[: len(self.constants)]
        self.test_legend_lines = self.test_legend_lines[: len(self.constants)]
        self.color_index -= len(self.test_lines)
        for line in list(self.test_lines):
            line.remove()
        plot = self.test_focus
        if plot is not None:
            plot.remove()
        self.test_lines = []
        for cam in range(cam_num):
            x_coords = np.linspace(0, self.x_size, num=arr_size)
            y_coords = list(np.full(arr_size, np.nan))
            (plot,) = self.axes.plot(
                x_coords, y_coords, lw=1, color=COLORS[self.color_index], label=f"_{cam_names[cam]}"
            )

            self.test_legend_lines.append(Line2D([], [], lw=1, color=COLORS[self.color_index]))
            self.test_legend_labels.append(cam_names[cam])
            self.test_lines.append(plot)
            self.color_index += 1
        y_coords = list(np.full(self.x_size, 0.5))
        x_coords = list(np.arange(0, self.x_size))
        (plot,) = self.axes.plot(x_coords, y_coords, color="white", lw=1, label="_Goal Focus")
        self.test_legend_lines.append(Line2D([], [], lw=1, color="white"))
        self.test_legend_labels.append("Goal Setting")
        self.test_focus = plot
        plot.set_visible(False)

    def plot_hardware(self, cam_vals, max_old: int, threshold: float = 0.5) -> None:
        plot = self.test_focus
        if plot is not None:
            plot.set_visible(True)
        for index, line in enumerate(self.test_lines):
            min_old = 0
            max_old = max_old
            min_new = -1
            max_new = 7
            y_points = np.array(cam_vals[index])
            y_points = (
                ((y_points - min_old) * (max_new - min_new)) / (max_old - min_old)
            ) + min_new
            line.set_ydata(y_points)

        self.draw()

    def remove_hardware(self) -> None:
        self.axes.legend(
            self.legend_lines,
            self.legend_labels,
            loc="upper left",
            fontsize=8,
            labelcolor=(0.1, 0.1, 0.1),
            edgecolor=(0.9, 0.9, 0.9),
            facecolor=(0.9, 0.9, 0.9),
            bbox_to_anchor=(-0.01, -0.01, 1.09, 1.09),
        )
        plot = self.test_focus
        plot.set_visible(False) if plot is not None else None

        for index, line in enumerate(self.test_lines):
            line.set_ydata(np.full(60, np.nan))
        self.draw()

    def set_constants(self, constants: list[str]) -> None:
        self.constant_labels = constants

    def reset(self):
        self.color_index = 0

    def update_label(self, index: int, new_label: str | int) -> None:
        if new_label == -1:
            self.legend_labels[index + len(self.constants)] = ""
        else:
            assert isinstance(new_label, str)
            self.legend_labels[index + len(self.constants)] = new_label
            # self.lines[index].set_label(new_label)

        self.axes.legend(
            self.legend_lines,
            self.legend_labels,
            loc="upper left",
            fontsize=8,
            labelcolor=(0.1, 0.1, 0.1),
            edgecolor=(0.9, 0.9, 0.9),
            facecolor=(0.9, 0.9, 0.9),
            bbox_to_anchor=(-0.01, -0.01, 1.09, 1.09),
        )
        self.draw()

    def setup_test_legend(self) -> None:
        self.axes.legend(
            self.test_legend_lines,
            self.test_legend_labels,
            loc="upper left",
            fontsize=8,
            labelcolor=(0.1, 0.1, 0.1),
            edgecolor=(0.9, 0.9, 0.9),
            facecolor=(0.9, 0.9, 0.9),
            bbox_to_anchor=(-0.01, -0.01, 1.09, 1.09),
        )
