import dash
import dash_daq as daq
import re
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output, State

from .layout import GraphLayout, InputGenerator, MultiOptionGenerator

from .util import compute

from ..constants import TAB_COUNT

class CallbackController(object):
  def __init__(self, app, tab_count):
    self.app = app
    self.tab_count = tab_count
    self.graph_layout = GraphLayout()
    self.input_generator = InputGenerator()
    self.multi_generator = MultiOptionGenerator()

  def graph_inputs(self):
    inputs = self.input_generator.graph_inputs(self.tab_count)
    return [[x, 'checked' if 'enabled' in x else'value'] for x in inputs]

  def setup_callbacks(self):
    self.setup_graph_callbacks()
    self.setup_input_callbacks()

  def setup_graph_callbacks(self):
    @self.app.callback(
      self._graph_update_outputs(),
      [Input(x, y) for x, y in self.graph_inputs()],
      self._graph_update_states(),
    )
    def graph_callback(*args):
      return self.update_graph(*args)

  def _graph_update_outputs(self):
    return [
      Output('damage-graph', 'figure'),
      *[Output('avg_display_{}'.format(i), 'children') for i in range(self.tab_count)],
      *[Output('std_display_{}'.format(i), 'children') for i in range(self.tab_count)],
    ]

  def _graph_update_states(self):
    return [
      State('damage-graph', 'figure'),
      *[State('avg_display_{}'.format(i), 'children') for i in range(self.tab_count)],
      *[State('std_display_{}'.format(i), 'children') for i in range(self.tab_count)],
    ]

  def setup_input_callbacks(self):
    for i in range(self.tab_count):
      self.setup_input_tab_callback(i)

  def setup_input_tab_callback(self, tab_index):
    self.disable_callback(tab_index)
    self.tab_name_callback(tab_index)
    self.shot_mods_callback(tab_index)
    self.hit_mods_callback(tab_index)
    self.wound_mods_callback(tab_index)
    self.save_mods_callback(tab_index)
    self.damage_mods_callback(tab_index)

  def disable_callback(self, tab_index):
    @self.app.callback(
      self._disable_outputs(tab_index),
      [Input('enabled_{}'.format(tab_index), 'checked')],
    )
    def disable_tab_options(enable):
        return [not enable] * 15

  def _disable_outputs(self, tab_index):
    ids = ['damage_mods_{}', 'save_mods_{}', 'wound_mods_{}', 'hit_mods_{}', 'shot_mods_{}',
           'ws_{}', 'toughness_{}', 'strength_{}', 'ap_{}', 'save_{}', 'invuln_{}', 'fnp_{}',
           'wounds_{}', 'shots_{}', 'damage_{}']
    return [Output(x.format(tab_index), 'disabled') for x in ids]


  def tab_name_callback(self, tab_index):
    @self.app.callback(
      Output('tab_{}'.format(tab_index), 'label'),
      [Input('tab_name_{}'.format(tab_index), 'value')],
    )
    def update_tab_name(value):
        return value if len(value) > 2 else 'Profile'


  def shot_mods_callback(self, tab_index):
    @self.app.callback(
      Output('shot_mods_{}'.format(tab_index), 'options'),
      [Input('shot_mods_{}'.format(tab_index), 'value')],
    )
    def update_shot_options(value):
      return self.multi_generator.shot_options(value or [])

  def hit_mods_callback(self, tab_index):
    @self.app.callback(
      Output('hit_mods_{}'.format(tab_index), 'options'),
      [Input('hit_mods_{}'.format(tab_index), 'value')],
    )
    def update_hit_options(value):
      return self.multi_generator.hit_options(value or [])

  def wound_mods_callback(self, tab_index):
    @self.app.callback(
      Output('wound_mods_{}'.format(tab_index), 'options'),
      [Input('wound_mods_{}'.format(tab_index), 'value')],
    )
    def update_wound_options(value):
      return self.multi_generator.wound_options(value or [])

  def save_mods_callback(self, tab_index):
    @self.app.callback(
      Output('save_mods_{}'.format(tab_index), 'options'),
      [Input('save_mods_{}'.format(tab_index), 'value')],
    )
    def update_save_options(value):
      return self.multi_generator.save_options(value or [])

  def damage_mods_callback(self, tab_index):
    @self.app.callback(
      Output('damage_mods_{}'.format(tab_index), 'options'),
      [Input('damage_mods_{}'.format(tab_index), 'value')],
    )
    def update_damage_options(value):
      return MultiOptionGenerator().damage_options(value or [])

  def parse_args(self, args):
    mapped_args = []
    for i in range(0, TAB_COUNT):
      tab_dict = {}
      tab_inputs = self.input_generator.gen_tab_inputs(i)
      trim_length = -1 * len('-{}'.format(i))
      for j, input_name in enumerate(tab_inputs):
        tab_dict[input_name[:trim_length]] = args[(len(tab_inputs)*i) + j]
      mapped_args.append(tab_dict)
    return mapped_args

  def update_graph(self, *args):
    graph_args = self.parse_args(args[:-1-self.tab_count])
    graph_data = args[-1-2*self.tab_count]['data']
    averages = list(args[-2*self.tab_count:-1*self.tab_count])
    stds = list(args[-1*self.tab_count:])

    if graph_data == [{}] * TAB_COUNT:
      tab_numbers = list(range(TAB_COUNT))
    else:
      tab_numbers = self.tabs_changed()
    for tab_number in range(TAB_COUNT):
      if tab_number in tab_numbers:
        data = compute(**graph_args[tab_number])
        graph_data[tab_number] = {
          'x': [i for i, x in enumerate(data['values'])],
          'y': [100*x for i, x in enumerate(data['values'])],
          'name': graph_args[tab_number]['tab_name'],
        }
        averages[tab_number] = 'Mean: {}'.format(round(data['mean'], 2))
        stds[tab_number] = 'σ: {}'.format(round(data['std'], 2))
      else:
        values = compute(**graph_args[tab_number])
        existing_data = graph_data[tab_number]
        existing_data['name'] = graph_args[tab_number]['tab_name']
        graph_data[tab_number] = existing_data
    max_len = max(max([len(x.get('x', [])) for x in graph_data]), 24)
    return [self.graph_layout.figure_template(graph_data, max_len)] + averages + stds

  def tabs_changed(self):
    ctx = dash.callback_context
    if not ctx:
      return list(range(TAB_COUNT))
    tabs = []
    for trigger in ctx.triggered:
      match = re.match(r'.*_(\d+).*', trigger['prop_id'])
      if match and 'tab_name' not in trigger['prop_id']:
        tabs.append(int(match.groups()[0]))
    return list(set(tabs))