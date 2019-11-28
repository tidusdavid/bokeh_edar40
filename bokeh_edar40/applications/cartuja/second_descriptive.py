from utils.rapidminer_proxy import call_webservice
from bokeh_edar40.visualizations.decision_tree import Node, Tree
import utils.bokeh_utils as bokeh_utils
from utils.generate_model_vars import load_or_create_model_vars

from bokeh.core.properties import value
from bokeh.models import ColumnDataSource, Div, HoverTool, GraphRenderer, StaticLayoutProvider, Rect, MultiLine, LinearAxis, Grid, Legend, LegendItem, Span, Label, BasicTicker, ColorBar, LinearColorMapper, PrintfTickFormatter, MonthsTicker, LinearAxis, Range1d
from bokeh.models.ranges import FactorRange
from bokeh.models.widgets import Select, Button, TableColumn, DataTable, CheckboxButtonGroup, Slider, TextInput
from bokeh.plotting import figure
from bokeh.layouts import layout, widgetbox, column, row
from bokeh.models.formatters import DatetimeTickFormatter
from bokeh.models.tickers import FixedTicker
from bokeh.transform import dodge, transform

import xml.etree.ElementTree as et
import pandas as pd
import numpy as np
from pandas.io.json import json_normalize
from collections import OrderedDict
from datetime import datetime as dt
import time
import random

def create_data_source_from_dataframe(df, group_value_name, group_value):
	"""Crea ColumnDataSource desde DataFrame agrupando los valores de una columna concreta según un valor
	Parameters:
		df (Dataframe): Dataframe de datos
		group_value_name (string): Nombre de columna donde buscar los valores a agrupar
		goup_value (string): Valor para agrupar los datos
	
	Returns:
		ColumnDataSource: ColumnDataSource con los datos correctamente agrupados
	"""
	df = df.loc[df[group_value_name].isin([group_value])]
	source = ColumnDataSource(df)

	return source

def calc_xoffset_corrects_plot(num_vals, bar_width):
    """Calcula el x offset de las barras según su ancho
    Parameters:
        num_vals (int): Número de valores a mostrar en la visualización
        bar_width (float): Ancho de cada barra del gráfico

    Returns:
        list: Valores de coordenadas X donde dibujar las barras del gráfico de aciertos
    """
    x_pos = []
    start_x = 0

    if num_vals % 2 != 0:
        start_x = 0
    else:
        start_x = bar_width

    # Computamos la posición de cada barra en el gráfico dependiendo del número de gráficos a mostrar por grupo de predicción
    for i in range(num_vals):
        if start_x == 0:
            x = start_x + i * (bar_width + bar_width/2) - ((bar_width*num_vals/2) + bar_width/2)
        else:
            x = start_x + i * (bar_width + bar_width/2) - ((2*bar_width*num_vals/2) - bar_width/2)
            if i >= num_vals/2:
                x = x + (bar_width/2)
        x_pos.append(x)

    return x_pos

def create_corrects_plot(df, target):
	"""Crea gráfica de aciertos
	Parameters:
		df: Dataframe con los datos de la matriz de confusión

	Returns:
		DataTable: Tabla de matriz de confusión
	"""
	xlabels = list(df.keys())
	source = ColumnDataSource(df)

	corrects_plot = figure(x_range=xlabels, plot_height=400, toolbar_location=None, sizing_mode='stretch_width', output_backend="webgl")

	bar_width = 0.1
	xloc = calc_xoffset_corrects_plot(num_vals=len(xlabels), bar_width=bar_width)
	for i, label in enumerate(xlabels):
		r = corrects_plot.vbar(x=dodge('Actual', xloc[i], range=corrects_plot.x_range), top=label, width=bar_width, source=source,
				color=bokeh_utils.BAR_COLORS_PALETTE[i], legend_label=label, name=xlabels[i])
		hover = HoverTool(tooltips=[
			("Predicción", "$name"),
			("Aciertos", "@$name")
		], renderers=[r])
		corrects_plot.add_tools(hover)
	corrects_plot.x_range.range_padding = 0.1
	corrects_plot.xgrid.grid_line_color = None
	corrects_plot.y_range.start = 0
	corrects_plot.legend.location = "top_right"
	corrects_plot.legend.orientation = "vertical"
	corrects_plot.legend.click_policy = 'hide'
	corrects_plot.legend.label_text_color = bokeh_utils.LABEL_FONT_COLOR

	corrects_plot.xaxis.major_label_orientation = np.pi/4
	corrects_plot.xaxis.major_label_text_color = bokeh_utils.LABEL_FONT_COLOR
	corrects_plot.yaxis.major_label_text_color = bokeh_utils.LABEL_FONT_COLOR

	corrects_plot.title.text = f'Gráfica de aciertos - {target}'
	corrects_plot.title.text_color = bokeh_utils.TITLE_FONT_COLOR
	corrects_plot.title.align = 'left'
	corrects_plot.title.text_font_size = '16px'
	corrects_plot.border_fill_color = bokeh_utils.BACKGROUND_COLOR
	corrects_plot.min_border_right = 15

	return corrects_plot

def create_attribute_weight_plot(df, target):
	"""Crea gráfica de importancia de predictores
	Parameters:
		df (Dataframe): Dataframe con los datos a mostrar en la visualización

	Returns:
		Figure: Gráfica de importancia de predictores
	"""

	df['colors'] = bokeh_utils.BAR_COLORS_PALETTE[:len(df['Attribute'].values)]

	source = ColumnDataSource(df)
	
	hover_tool = HoverTool(
		tooltips = [
			('Peso', '@Weight{(0.00)}')
		]
		)

	weight_plot = figure(plot_height=400, toolbar_location=None, sizing_mode='stretch_width', x_range=df['Attribute'].values, output_backend="webgl")

	weight_plot.vbar(x='Attribute', top='Weight', source=source, width=0.9, line_color='white', fill_color='colors')

	weight_plot.xaxis.major_label_text_color = bokeh_utils.LABEL_FONT_COLOR

	weight_plot.yaxis.major_label_text_color = bokeh_utils.LABEL_FONT_COLOR

	weight_plot.y_range.start = 0

	weight_plot.title.text = f'Importancia de los predictores - {target}'
	weight_plot.title.text_color = bokeh_utils.TITLE_FONT_COLOR
	weight_plot.title.align = 'left'
	weight_plot.title.text_font_size = '16px'
	weight_plot.border_fill_color = bokeh_utils.BACKGROUND_COLOR

	weight_plot.add_tools(hover_tool)

	return weight_plot

def create_confusion_matrix(df):
	"""Crea tabla de matriz de confusión
	Parameters:
		data_dict (dict): Diccionario con los datos a mostrar en la visualización

	Returns:
		Figure: Gráfica de importancia de predictores
	"""
	# Tranformar el DataFrame en un stack
	data_dict = df.stack().rename("value").reset_index()

	# Paleta de colores
	# colors = ['#f7fbff','#deebf7','#c6dbef','#9ecae1','#6baed6','#4292c6','#2171b5','#08519c','#08306b']
	colors = ['#f7fbff','#deebf7','#c6dbef','#9ecae1','#6baed6','#4292c6','#2171b5','#08519c']

	# Had a specific mapper to map color with value
	mapper = LinearColorMapper(palette=colors, low=data_dict.value.min(), high=data_dict.value.max())

	# Define a figure
	p = figure(
		plot_height=270,
		x_range=list(data_dict.Actual.drop_duplicates()),
		y_range=list(reversed(data_dict.Prediction.drop_duplicates())),
		toolbar_location=None,
		tools="",
		x_axis_location="above",
		x_axis_label="Actual Label",
		y_axis_label="Predicted Label",
		sizing_mode='stretch_width',
		output_backend="webgl")
	p.xaxis.axis_line_color = None
	p.yaxis.axis_line_color = None
	p.xaxis.major_label_orientation = np.pi/4
	
	# Create rectangle for heatmap
	p.rect(
		x="Actual",
		y="Prediction",
		width=1,
		height=1,
		source=ColumnDataSource(data_dict),
		line_color=None,
		fill_color=transform('value', mapper))
	p.text(x="Actual",
		y="Prediction", text='value', text_align="center", text_baseline="middle", source=ColumnDataSource(data_dict))
	
	p.border_fill_color = bokeh_utils.BACKGROUND_COLOR	
	p.background_fill_color = bokeh_utils.BACKGROUND_COLOR

	# Add legend
	color_bar = ColorBar(
    color_mapper=mapper,
    location=(0, 0),
    ticker=BasicTicker(desired_num_ticks=len(colors)))
	color_bar.background_fill_color = bokeh_utils.BACKGROUND_COLOR

	p.add_layout(color_bar, 'right')

	return p

#TODO Eliminar despues de nuevos servicios RapidMiner
def create_model_menu(new_models = False, new_variables = []):
	"""Crea menú de selección de variables para modelización del árbol de decisión

	Returns:
		Button: Botón del menú de selección
		Select: Panel de selección de variable del menú de selección
	"""

	if new_models == False:
		variables_file = open('resources/model_variables.txt', 'r')
		variables_file_lines = variables_file.readlines()

		option_values = [line.rstrip('\n') for line in variables_file_lines]
		
		option_values.sort(key=lambda option_value:(option_value[:2]!='O_', option_value))
	else:
		option_values = new_variables

	selected_value = 'Calidad_Agua'

	title = create_div_title('Modelo')
	select = Select(value=selected_value, options=option_values, height=35, sizing_mode='stretch_width')
	button = Button(label='Modelizar', button_type='primary', height=45)

	return title, button, select

#TODO Descomentar despues de crear nuevos servicios RapidMiner
# def create_model_menu(model_variables = []):
# 	"""Crea menú de selección de variables para modelización del árbol de decisión
# 	Parameters:
# 		model_variables: Lista con las variables para modelización

# 	Returns:
# 		Button: Botón del menú de selección
# 		Select: Panel de selección de variable del menú de selección
# 	"""

# 	option_values = new_variables

# 	selected_value = 'Calidad_Agua'

# 	title = create_div_title('Modelo')
# 	select = Select(value=selected_value, options=option_values, height=35)
# 	button = Button(label='Modelizar', button_type='primary', height=45)

# 	return title, button, select


def create_decision_tree_graph_renderer(plot, tree):
	"""Crea el renderizador del gráfico del árbol de decisión. Para ello se deben especificar configuraciones como: indices o identificadores
	de los nodos, colores de los nodos, tipos de figura de los nodos, tipos de figura de relación entre nodo y las relaciones entre los nodos (inicio y final)
	Parameters:
		plot (Figure): Figura Bokeh donde se muestra el árbol de decisión
		tree (Tree): Estructura del árbol de decisión a mostrar

	Returns:
		GraphRenderer: Renderizador del gráfico del árbol de decisión
	"""
	
	node_indices = [node.id for node in tree.node_list]
	node_colors = [node.color for node in tree.node_list]

	start, end = tree.get_nodes_relations()
	x, y = tree.get_layout_node_positions(plot)
	graph_layout = dict(zip(node_indices, zip(x,y)))

	graph = GraphRenderer()

	graph.node_renderer.data_source.add(node_indices, 'index')
	graph.node_renderer.data_source.add(node_colors, 'color')
	graph.node_renderer.glyph = Rect(height=0.15, width=0.2, fill_color='color')
	graph.edge_renderer.glyph = MultiLine(line_color='#b5b8bc', line_alpha=0.8, line_width=5)

	graph.edge_renderer.data_source.data = dict(
    	start=start,
    	end=end)

	graph.layout_provider = StaticLayoutProvider(graph_layout=graph_layout)

	return graph

def append_labels_to_decision_tree(plot, graph, tree):
	"""Añade los textos necesarios (nombre del nodo y condición de relación) al gráfico del árbol de visualización
	Parameters:
		plot (Figure): Figura Bokeh donde se muestra el árbol de decisión
		graph (GraphRenderer): Renderizador del gráfico del árbol de decisión
		tree (Tree): Estructura del árbol de decisión a mostrar

	Returns:
		Figure: Gráfica del árbol de decisión
	"""
	plot.renderers = []
	plot.renderers.append(graph)
	
	node_text_x, node_text_y, node_text = tree.get_node_text_positions()
	plot.text(node_text_x, node_text_y, text=node_text, text_font_size={'value': '10pt'}, text_align='center')

	middle_x, middle_y, middle_text = tree.get_line_text_positions()
	plot.text(middle_x, middle_y, text=middle_text, text_font_size={'value': '11pt'}, text_align='center')
	return plot


def create_decision_tree_plot():
	"""Crea la figura para visualizar el árbol de decisión

	Returns:
		Figure: Gráfica del árbol de decisión
	"""
	plot = figure(x_range=(-1.1,1.1), y_range=(0,1.1), toolbar_location=None, plot_height=500, sizing_mode='stretch_width', output_backend="webgl")

	plot.axis.visible = False
	plot.xgrid.grid_line_color = None
	plot.ygrid.grid_line_color = None
	plot.border_fill_color = bokeh_utils.BACKGROUND_COLOR	
	plot.background_fill_color = bokeh_utils.BACKGROUND_COLOR
	plot.outline_line_color = None

	return plot

def create_outlier_plot(df):
	"""Crea gráfica de outliers
	Parameters:
		df (Dataframe): Dataframe con los datos a mostrar en la visualización

	Returns:
		Figure: Gráfica de outliers
	"""

	hover_tool = HoverTool(
		tooltips = [
			('Fecha', '@timestamp{%F}'),
			('Outlier', '@outlier')
		],
		formatters = {
			'timestamp': 'datetime',
		},
		mode = 'mouse'
		)

	outlier_plot = figure(plot_height=400, toolbar_location=None, sizing_mode='stretch_width', x_axis_type='datetime', output_backend="webgl")

	df['timestamp'] = pd.to_datetime(df['timestamp'])
	df['outlier'] = pd.to_numeric(pd.Series(df['outlier'].values))

	source_cluster_0 = create_data_source_from_dataframe(df, 'cluster', 'cluster_0')
	source_cluster_1 = create_data_source_from_dataframe(df, 'cluster', 'cluster_1')
	source_cluster_2 = create_data_source_from_dataframe(df, 'cluster', 'cluster_2')
	source_cluster_3 = create_data_source_from_dataframe(df, 'cluster', 'cluster_3')

	# outlier_plot.circle(x='timestamp', y='outlier', source=source_cluster_0, color=bokeh_utils.LINE_COLORS_PALETTE[0], size=6, legend_label='Cluster 0')
	# outlier_plot.circle(x='timestamp', y='outlier', source=source_cluster_1, color=bokeh_utils.LINE_COLORS_PALETTE[1], size=6, legend_label='Cluster 1')
	# outlier_plot.circle(x='timestamp', y='outlier', source=source_cluster_2, color=bokeh_utils.LINE_COLORS_PALETTE[2], size=6, legend_label='Cluster 2')
	# outlier_plot.circle(x='timestamp', y='outlier', source=source_cluster_3, color=bokeh_utils.LINE_COLORS_PALETTE[3], size=6, legend_label='Cluster 3')
	size = 5
	alpha = 0.4
	outlier_plot.circle(x='timestamp', y='outlier', source=source_cluster_0, color=bokeh_utils.LINE_COLORS_PALETTE[0], alpha=alpha, size=size, legend_label='Cluster 0')
	outlier_plot.circle(x='timestamp', y='outlier', source=source_cluster_1, color=bokeh_utils.LINE_COLORS_PALETTE[1], alpha=alpha, size=size, legend_label='Cluster 1')
	outlier_plot.circle(x='timestamp', y='outlier', source=source_cluster_2, color=bokeh_utils.LINE_COLORS_PALETTE[2], alpha=alpha, size=size, legend_label='Cluster 2')
	outlier_plot.circle(x='timestamp', y='outlier', source=source_cluster_3, color=bokeh_utils.LINE_COLORS_PALETTE[3], alpha=alpha, size=size, legend_label='Cluster 3')


	outlier_plot.xaxis.major_label_text_color = bokeh_utils.LABEL_FONT_COLOR
	outlier_plot.yaxis.major_label_text_color = bokeh_utils.LABEL_FONT_COLOR

	outlier_plot.legend.location = 'top_left'
	outlier_plot.legend.orientation = 'horizontal'
	outlier_plot.legend.click_policy = 'hide'
	outlier_plot.legend.label_text_color = bokeh_utils.LABEL_FONT_COLOR

	outlier_plot.xaxis[0].formatter = DatetimeTickFormatter(years=['%Y'])

	outlier_plot.title.text = 'Probabilidad de Outliers'
	outlier_plot.title.text_color = bokeh_utils.TITLE_FONT_COLOR
	outlier_plot.title.align = 'left'
	outlier_plot.title.text_font_size = '16px'
	outlier_plot.border_fill_color = bokeh_utils.BACKGROUND_COLOR
	outlier_plot.add_tools(hover_tool)
	outlier_plot.min_border_right = 15

	return outlier_plot

def create_prediction_plot(df):
	"""Crea gráfica de predicción a futuro
	Parameters:
		df (Dataframe): Dataframe con los datos a mostrar en la visualización

	Returns:
		Figure: Gráfica de de predicción a futuro
	"""

	hover_tool = HoverTool(
		tooltips = [
			('Fecha', '$x{%b %Y}'),
			('Predicción', '@Prediction')
		],
		formatters = {
			'$x': 'datetime',
		},
		mode = 'mouse'
		)

	# Estructuración de los tipos de datos del dataframe
	df['añomes'] = pd.to_datetime(df['añomes'], format='%m/%d/%y %I:%M %p')
	df['Prediction'] = pd.to_numeric(pd.Series(df['Prediction'].values))

	prediction_plot = figure(plot_height=400, toolbar_location=None, sizing_mode='stretch_width', x_axis_type='datetime', output_backend="webgl")
	
	source_cluster_0 = create_data_source_from_dataframe(df, 'cluster', 'cluster_0')
	source_cluster_1 = create_data_source_from_dataframe(df, 'cluster', 'cluster_1')
	source_cluster_2 = create_data_source_from_dataframe(df, 'cluster', 'cluster_2')
	source_cluster_3 = create_data_source_from_dataframe(df, 'cluster', 'cluster_3')

	x_axis_tick_vals = source_cluster_0.data['añomes'].astype(int) / 10**6

	prediction_plot.line(x='añomes', y='Prediction', source=source_cluster_0, line_width=2, line_color=bokeh_utils.LINE_COLORS_PALETTE[0], legend_label='Cluster 0')
	prediction_plot.line(x='añomes', y='Prediction', source=source_cluster_1, line_width=2, line_color=bokeh_utils.LINE_COLORS_PALETTE[1], legend_label='Cluster 1')
	prediction_plot.line(x='añomes', y='Prediction', source=source_cluster_2, line_width=2, line_color=bokeh_utils.LINE_COLORS_PALETTE[2], legend_label='Cluster 2')
	prediction_plot.line(x='añomes', y='Prediction', source=source_cluster_3, line_width=2, line_color=bokeh_utils.LINE_COLORS_PALETTE[3], legend_label='Cluster 3')

	prediction_plot.xaxis.major_label_orientation = np.pi/4
	prediction_plot.xaxis.major_label_text_color = bokeh_utils.LABEL_FONT_COLOR

	prediction_plot.yaxis.major_label_text_color = bokeh_utils.LABEL_FONT_COLOR

	prediction_plot.legend.location = 'top_left'
	prediction_plot.legend.orientation = 'horizontal'
	prediction_plot.legend.click_policy = 'hide'
	prediction_plot.legend.label_text_color = bokeh_utils.LABEL_FONT_COLOR
	prediction_plot.xaxis[0].formatter = DatetimeTickFormatter(months=['%b %Y'])
	prediction_plot.xaxis[0].ticker = FixedTicker(ticks=list(x_axis_tick_vals))
	# Linea vertical para definir el horizonte de predicción
	prediction_date = time.mktime(dt(2019, 2, 1, 0, 0, 0).timetuple())*1000
	vline = Span(location=prediction_date, dimension='height', line_color='gray', line_alpha=0.6, line_dash='dotted', line_width=2)
	prediction_plot.add_layout(vline)
	# Etiqueta linea horizontal
	vlabel = Label(x=prediction_date, y=40, text='→Predicción', text_color='gray', text_alpha=0.6, text_font_size='14px')
	prediction_plot.add_layout(vlabel)

	prediction_plot.title.text = 'Predicción de los clusters a futuro'
	prediction_plot.title.text_color = bokeh_utils.TITLE_FONT_COLOR
	prediction_plot.title.align = 'left'
	prediction_plot.title.text_font_size = '16px'
	prediction_plot.border_fill_color = bokeh_utils.BACKGROUND_COLOR
	prediction_plot.add_tools(hover_tool)
	prediction_plot.min_border_right = 15

	return prediction_plot

def create_df_confusion(df_original):
	"""Crea el dataframe para la matriz de confusion
	Parameters:
		df_original: Dataframe con los datos sin organizar de la matriz de confusión
	
	Returns:
		df: Dataframe con los datos convertidos para la matriz de confusion
	"""
	
	# Slicing dataframe for confussion matrix and removing redundant text
	df = df_original
	df['predicted'].replace(regex="pred ", value="", inplace=True)
	
	df = df.set_index("predicted")
	df.columns.name = 'Actual'
	df.index.name = 'Prediction'
	df.columns = df.columns.str.replace(r"true ", "")
	df = df.transpose()

	# Converting dataframe to right format
	df = df.apply(pd.to_numeric)
	return df

def create_decision_tree_data(df, target='Calidad_Agua'):
	"""Crea el Tree del decision tree
	Parameters:
		df: Dataframe con los datos sin organizar del arbol de decision
	
	Returns:
		tree: Arbol listo para graficar con sus nodos
	"""
	color_palette = {'cluster_0': bokeh_utils.BAR_COLORS_PALETTE[0], 'cluster_1': bokeh_utils.BAR_COLORS_PALETTE[1], 'cluster_2': bokeh_utils.BAR_COLORS_PALETTE[2], 'cluster_3': bokeh_utils.BAR_COLORS_PALETTE[3], 
	'range1': bokeh_utils.BAR_COLORS_PALETTE[0], 'range2': bokeh_utils.BAR_COLORS_PALETTE[1], 'range3': bokeh_utils.BAR_COLORS_PALETTE[2], 'range4': bokeh_utils.BAR_COLORS_PALETTE[3], 'range5': bokeh_utils.BAR_COLORS_PALETTE[4]}

	tree = Tree()
	count = 0
	for j, elements in enumerate(df['Condition']):
		leaf = elements.split(' & ')
		# print(leaf)
		for i in range(len(leaf)+1):
			if i < len(leaf):
				node = leaf[i].split(' ', 1)
				# print(node)
				node_name = node[0]
				tree_node = Node(count+1, node_name, i, '#c2e8e0')
				# print(f"tree_node = Node({count+1}, '{node_name}', {i}, '#c2e8e0')")
				tree.order_nodes(tree_node, node[1])
				# print(f"tree.order_nodes(tree_node, '{node[1]}')")
			else:
				if target == 'Calidad_Agua':
					node_name = df['Prediction'][j]
					color = color_palette[df['Prediction'][j]]
				else:
					range_split = df['Prediction'][j].split(' ', 1)
					# print(f'range_split[0]:{range_split[0]}')
					# print(f'range_split[1]:{range_split[1]}')
					node_name = range_split[0] + '\n' + range_split[1]
					color = color_palette[range_split[0]]
				# print(f"tree_node = Node({count+1}, '{node_name}', {i}, '{color}')")
				tree_node = Node(count+1, node_name, i, color)
				tree.order_nodes(tree_node, node[1])
				# print(f"tree.order_nodes(tree_node, '{node[1]}')")
			count = count + 1

	return tree


def create_daily_pred_plot(df_original, target='Calidad_Agua'):
	"""Crea gráfica de predicciones contra valores reales
	Parameters:
		df_original (Dataframe): Dataframe con los datos a mostrar en la visualización

	Returns:
		Figure: Gráfica de predicciones contra valores reales
	"""
	df = df_original
	df = df.rename(columns={target: 'real', f'prediction({target})': 'prediction'})
	bins = list(df['real'].unique())
	df['timestamp'] = pd.to_datetime(df['timestamp'], format='%m/%d/%y').sort_values()
	df = df.set_index('timestamp')
	df = df.groupby(df.index).first()
	df = df['2018-01-01':'2019-01-31']

	if target=='Calidad_Agua':
		df.replace(regex=['cluster_'], value='', inplace=True)
	else:
		df.replace(regex=[r'\[.*\]', 'range'], value='', inplace=True)
	
	df[['real','prediction']] = df[['real','prediction']].astype(int)
	df['error'] = abs(df['real']-df['prediction'])

	TOOLTIPS = [
		('Fecha', "@timestamp{%F}"),
		('Real', '@real'),
		("Predicho", "@prediction")
	]
	hover_tool = HoverTool(tooltips = TOOLTIPS, formatters={'timestamp': 'datetime'})

	source = ColumnDataSource(df)

	daily_pred_plot = figure(plot_height=200, toolbar_location='right', sizing_mode='stretch_width', x_axis_type='datetime',
							tools='pan, box_zoom, reset', output_backend="webgl")
	daily_pred_plot.toolbar.logo = None
	# Se añade un nuevo eje Y para el error
	# daily_pred_plot.extra_y_ranges = {'y_error': Range1d(start=0, end=df['real'].max()-df['real'].min())}
	daily_pred_plot.extra_y_ranges = {'y_error': Range1d(start=0, end=len(bins))}
	daily_pred_plot.add_layout(LinearAxis(y_range_name='y_error', axis_label='Error', ticker=list(range(len(bins)))), 'right')

	daily_pred_plot.line(x='timestamp', y='real', source=source, line_width=2, line_color='#392FCC', line_alpha=0.8, legend_label='Real')
	daily_pred_plot.line(x='timestamp', y='prediction', source=source, line_width=2, line_color='#CA574D', line_alpha=0.8, line_dash='dashed', legend_label='Predicción')
	daily_pred_plot.line(x='timestamp', y='error', source=source, line_width=2, line_color='green', line_alpha=0.4, legend_label='Error', y_range_name='y_error')


	daily_pred_plot.xaxis.major_label_orientation = np.pi/4
	daily_pred_plot.xaxis.formatter = DatetimeTickFormatter(months=['%b %Y'])
	daily_pred_plot.xaxis.ticker = MonthsTicker(months=list(range(1,13)))
	
	if target == 'Calidad_Agua':
		daily_pred_plot.yaxis[0].ticker =  list(range(len(bins)))
		daily_pred_plot.yaxis[0].formatter = PrintfTickFormatter(format="Cluster %u")
	else:
		daily_pred_plot.yaxis[0].ticker =  list(range(1,1+len(bins)))
		daily_pred_plot.y_range=Range1d(0, len(bins)+1) # Manipulates y_range
		daily_pred_plot.yaxis[0].formatter = PrintfTickFormatter(format="Range %u")
	
	daily_pred_plot.ygrid.minor_grid_line_color = None
	daily_pred_plot.xaxis.major_label_text_color = bokeh_utils.LABEL_FONT_COLOR
	daily_pred_plot.yaxis.major_label_text_color = bokeh_utils.LABEL_FONT_COLOR

	daily_pred_plot.legend.location = 'top_left'
	daily_pred_plot.legend.orientation = 'horizontal'
	daily_pred_plot.legend.click_policy = 'hide'
	daily_pred_plot.legend.label_text_color = bokeh_utils.LABEL_FONT_COLOR

	daily_pred_plot.title.text = f'Predicciones diarias - {target}'
	daily_pred_plot.title.text_color = bokeh_utils.TITLE_FONT_COLOR
	daily_pred_plot.title.align = 'left'
	daily_pred_plot.title.text_font_size = '16px'
	daily_pred_plot.border_fill_color = bokeh_utils.BACKGROUND_COLOR
	daily_pred_plot.add_tools(hover_tool)
	daily_pred_plot.min_border_right = 15

	return daily_pred_plot

def create_div_title(title = ''):
	"""Crea el título para un objeto de la interfaz bokeh
	Parameters:
		title: String con el título a crear
	
	Returns:
		div_title: Objeto Div de bokeh con el título creado
	"""

	div_title = Div(
				text=title,
				style={
					'font-weight': 'bold',
					'font-size': '16px',
					'color': bokeh_utils.TITLE_FONT_COLOR,
					'margin-top': '2px',
					'font-family': 'inherit'},
				height=20,
				sizing_mode='stretch_width')
	
	return div_title

def create_df_sliders(weight_df, pred_df):
	"""Crea el dataframe que contiene los valores estadisticos para crear los sliders
	Parameters:
		weight_df: Dataframe con las variables influyentes
		pred_df: Dataframe con las predicciones diarias
	Returns:
		slider_df: Dataframe con los valores minimo, medio y máximo para la creación de sliders
	"""

	var_influyentes = list(weight_df['Attribute'])
	pred_df_stats=pred_df[var_influyentes].describe()
	df_sliders = pred_df_stats.loc[['min', 'mean', 'max']]

	return df_sliders

class DynamicRow:
	"""Clase DynamicRow para representar una fila dinámica con slider y textbox
	
	Attributes:
		start: Valor inicial del slider
		end: Valor final del slider
		value: Valor por defecto del slider y el textbox
		title: Título del slider
	"""
	def __init__(self, start, end, value, title):
		self.start = start
		self.end = end
		self.value = value
		self.title = title
		self.slider = Slider(start=self.start, end=self.end, value=self.value, step=0.1, title=self.title, max_width=280)
		self.text_input = TextInput(value=f"{self.value:.2f}", max_width=100)
		self.dyn_row = row([self.slider, self.text_input], sizing_mode='stretch_height')
		self.slider.on_change('value',self.slider_handler)
		self.text_input.on_change('value',self.text_handler)
	def slider_handler(self, attrname, old, new):
		self.text_input.value = f"{new:.2f}"
	def text_handler(self, attrname, old, new):
		self.slider.value = float(new)

class DynamicWidget:
	"""Clase DynamicWidget para representar widget dinámicos con sliders y textbox de simulación
	
	Attributes:
		df: Dataframe con las estadisticas para min, mean, max de los sliders
		target: Target de simulación
	"""
	def __init__(self, df, target):
		self.df = df
		self.target = target
		self.new_rows = OrderedDict([])
		self.columns = column([])
		self.var_title = Div(text='<b>Variables de entrada</b>')
		for col in list(self.df.keys()):
			delta = (self.df[col]['max']-self.df[col]['min']) * 0.1
			self.new_rows.update({f'row_{col}': DynamicRow(start=max(0,self.df[col]['min']-delta),
                                    						end=self.df[col]['max']+delta,
                                          					value=self.df[col]['mean'],
                                          					title=col)})
			self.columns.children.append(self.new_rows[f'row_{col}'].dyn_row)
		self.button_simulate = Button(label="Simular", button_type="primary")
		self.button_simulate.on_click(self.simulate)
		self.sim_target = Div(text=f'<b>{self.target}:</b>')
		self.wb = widgetbox([self.var_title, self.columns, self.sim_target, self.button_simulate], max_width=200)

	def simulate(self, new):
		"""Callback que simula y obtiene una predicción con los valores fijados por el usuario en los sliders
		"""
		vars_influyentes = {}
		for col in list(self.df.keys()):
			vars_influyentes.update({col: round(self.new_rows[f'row_{col}'].slider.value,2)})
		self.sim_target.text = f'<b>{self.target}</b>: cluster_{random.randint(0,4)}'
		print(vars_influyentes)

        # TODO json_simul = call_webservice(url='http://rapidminer.vicomtech.org/api/rest/process/EDAR_Cartuja_Simulacion_JSON?,
		#				                    username='rapidminer',
		#				                    password='rapidminer',
		# 				                    parameters={'Modelo': self.target, 'Variables_influyentes': vars_influyentes},
		# 				                    out_json=True)

class DynamicOptimRow:
	"""Clase DynamicOptimRow para representar una fila dinámica con cada variable influyente y sus respectivos combobox para las restricciones
	
	Attributes:
		var_title: Título de la restricción
	"""
	def __init__(self, var_title):
		self.var_title = var_title
		self.var_row_title = Div(text=f'{self.var_title}:')
		self.var_found_value = Div(text='')
		self.low_condition_select = Select(title='Condición1', value='-', options=['<', '≤', '=', '≥', '>', '-'], max_width=80, min_width=80)
		# self.low_inter_text = TextInput(title='Valor1', value='', max_width=80, min_width=80, visible=False)
		# self.high_condition_select = Select(title='Condición2', value='-', options=['<', '≤', '≥', '>', '-'], max_width=80, min_width=80, visible=False)
		# self.high_inter_text = TextInput(title='Valor2', value='', max_width=80, min_width=80, visible=False)
		self.low_inter_text = TextInput(title='Valor1', value='', max_width=80, min_width=80)
		self.high_condition_select = Select(title='Condición2', value='-', options=['<', '≤', '≥', '>', '-'], max_width=80, min_width=80)
		self.high_inter_text = TextInput(title='Valor2', value='', max_width=80, min_width=80)

		self.target_col = row(children=[self.var_row_title, self.var_found_value],
							  sizing_mode='stretch_width',
							  max_width=200, min_width=200)
		self.dyn_row = row([self.target_col,
							self.low_condition_select,
							self.low_inter_text,
							self.high_condition_select,
							self.high_inter_text], sizing_mode='stretch_width')
# 		self.low_condition_select.on_change('value', self.low_select_handler)
# 		self.high_condition_select.on_change('value', self.high_select_handler)
# 	def low_select_handler(self, attr, old, new):
# #             print(f'attr: {attr}, old: {old}, {new}')
# 		if new=='-':
# 			self.low_inter_text.visible=False
# 			self.high_condition_select.value = '-'
# 			self.high_condition_select.visible = False
# 		elif new=='=':
# 			self.low_inter_text.visible=True
# 			self.high_condition_select.value = '-'
# 			self.high_condition_select.visible = False
# 		else:
# 			self.low_inter_text.visible=True
# 			self.high_condition_select.visible = True
# 	def high_select_handler(self, attr, old, new):
# #             print(f'attr: {attr}, old: {old}, {new}')
# 		if new=='-':
# 			self.high_inter_text.visible = False
# 		else:
# 			self.high_inter_text.visible = True

class DynamicOptimWidget:
	"""Clase DynamicOptimWidget para representar widget dinámicos con todas las restricciones para optimizar
	
	Attributes:
		target: Target de optimización
		possible_targets: Lista de posibles clusters/rangos a optimizar
		var_influyentes: Lista variables influyentes que calculadas por el optimizador
	"""
	def __init__(self, target, possible_targets, var_influyentes):
		self.target = target
		self.possible_targets = possible_targets
		self.var_influyentes = var_influyentes
		self.target_title = create_div_title(f'Optimización - {self.target}')
		self.objective_select = Select(title='Objetivo', value='min', options=['min', 'max'])
		self.target_select = Select(title='Target', value=possible_targets[-1], options=possible_targets, min_width=110)
		self.restrict_title = Div(text='<b>Restricciones</b>')
		self.dyn_row_list = OrderedDict([])
		self.columns = column([], sizing_mode='stretch_width')
		for var in self.var_influyentes:
			self.dyn_row_list.update({var:DynamicOptimRow(var_title=var)})
			self.columns.children.append(self.dyn_row_list[var].dyn_row)
		self.button_optimize = Button(label="Optimizar", button_type="primary", max_width=180)
		self.button_optimize.on_click(self.optimizar)
		self.wb = widgetbox([self.target_title,
							row([self.objective_select, self.target_select], sizing_mode='stretch_width'),
							self.restrict_title,
							self.columns,
							self.button_optimize], sizing_mode='stretch_width', max_width=300)
	def optimizar(self):
		"""Callback que optimiza y obtiene los valores de las variables influyentes según objetivo fijado
		"""
		restricciones = {}
		for var in self.var_influyentes:
			
			condicion1 = self.dyn_row_list[var].low_condition_select.value
			condicion2 = self.dyn_row_list[var].high_condition_select.value
			
			dict_condicion1 = self.create_dict_condicion(num_condicion=1,
															condicion=condicion1,
															val_condicion_raw=self.dyn_row_list[var].low_inter_text.value)
			dict_condicion2 = self.create_dict_condicion(num_condicion=2,
															condicion=condicion2,
															val_condicion_raw=self.dyn_row_list[var].high_inter_text.value)
			if dict_condicion1:
				dict_condicion1.update(dict_condicion2)
				restricciones.update({var: dict_condicion1})
			self.dyn_row_list[var].var_found_value.text = f'<b>{round(random.uniform(0,20),2)}</b>'
		arg_target = {'variable':self.target, 'valor':self.target_select.value, 'objetivo': self.objective_select.value}
		print(f'Target: {arg_target}')
		print(f'Restricciones: {restricciones}')

		# TODO json_optim = call_webservice(url='http://rapidminer.vicomtech.org/api/rest/process/EDAR_Cartuja_Optimizacion_JSON?,
		#				                    username='rapidminer',
		#				                    password='rapidminer',
		# 				                    parameters={'Target': arg_target, 'Restricciones': restricciones},
		# 				                    out_json=True)
	def create_dict_condicion(self, num_condicion, condicion, val_condicion_raw):
		"""Función que crea el diccionario con la restricción especificada

		Parameters:
			num_condicion: Número de la condición (posible 1 o 2)
			condicion: Tipo de condición (<, >, <=, >=, =, -)
			val_condicion_raw: Valor ingresado por el usuario de la condición sin procesar
		
		Returns:
			dict_condicion: Diccionario con la restricción creada
		"""
#             print(f'num_condicion: {num_condicion}, condicion: {condicion}, val_condicion_raw: {val_condicion_raw}')
		if condicion != '-':
			try:
				val_condicion = max(0, float('0'+val_condicion_raw))
			except:
				val_condicion = 0
			dict_condicion = {f'condicion{num_condicion}': condicion,
								f'val_condicion{num_condicion}': val_condicion}
		else:
			dict_condicion = {}
		return dict_condicion

def modify_second_descriptive(doc):
	# Captura de los argumentos pasados desde flask
	args = doc.session_context.request.arguments
	try:
		periodo = int(args.get('periodo')[0])
		# tipo_var = str(args.get('tipo_var')[0])
	except:
		periodo = 0
		# tipo_var = 'rend'
	# print(f'periodo: {periodo}, tipo_var: {tipo_var}')
	print(f'periodo: {periodo}')

	# Creación/Carga en RAM del diccionario con las variables a modelizar
	total_model_dict = load_or_create_model_vars(model_vars_file = 'resources/total_model_dict.pkl', 
												mask_file = 'resources/model_variables_mask.xlsx',
												sheets = ['ID_INFLUENTE',
															'ID_BIOS',
															'ID_FANGOS',
															'ID_HORNO',
															'ID_EFLUENTE',
															'ID_ELECTRICIDAD',
															'YOKO',
															'ANALITICA'],
												cols = ['OUT', 'IN', 'MANIPULABLES', 'PROCESOS_IN'],
												force_create=False)

	# Inicialización del diccionario ordenado para almacenar los modelos creados
	models = OrderedDict([])
	
	# Llamada al webservice de RapidMiner
	json_perfil_document = call_webservice('http://rapidminer.vicomtech.org/api/rest/process/EDAR_Cartuja_Perfil_Out_JSON?', 'rapidminer', 'rapidminer', out_json=True)
	
	# Extracción de los datos web
	df_perfil = [json_normalize(data) for data in json_perfil_document]
	
	# Asignación de los datos web a su variable correspondiente
	prediction_df = df_perfil[3]
	outlier_df = df_perfil[4]

	# Creación de los gráficos y widgets permanentes en la interfaz
	prediction_plot = create_prediction_plot(prediction_df)
	outlier_plot = create_outlier_plot(outlier_df)
	simulation_title = create_div_title('Simulación y Optimización de modelos')
	model_title, add_model_button, model_select_menu = create_model_menu()
	model_title_new, add_model_button_new, model_select_menu_new = create_model_menu(new_models=True, new_variables=list(total_model_dict.keys()))
	recreate_button = Button(label='Recrear', button_type='success', height=35, max_width=190)
	model_select_menu_new.max_width=190
	model_select_wb = widgetbox([model_title, model_select_menu, row([model_select_menu_new, recreate_button], sizing_mode='stretch_width', max_width=400) , add_model_button], max_width=400, sizing_mode='stretch_width')
	created_models_title = create_div_title('Modelos creados')
	created_models_checkbox = CheckboxButtonGroup(labels=list(models.keys()), height=35)
	created_models_checkbox.active = [0]
	delete_model_button = Button(label='Eliminar', button_type='danger', height=45, max_width=200)
	created_models_wb = widgetbox([created_models_title, created_models_checkbox], max_width=900, sizing_mode='stretch_width')
	# Callback para crear nuevamente el listado de variables de la mascara
	def recreate_callback():
		print('Recreando lista de variables para modelizar')
		nonlocal total_model_dict
		total_model_dict = load_or_create_model_vars(model_vars_file = 'resources/total_model_dict.pkl', 
												mask_file = 'resources/model_variables_mask.xlsx',
												sheets = ['ID_INFLUENTE',
															'ID_BIOS',
															'ID_FANGOS',
															'ID_HORNO',
															'ID_EFLUENTE',
															'ID_ELECTRICIDAD',
															'YOKO',
															'ANALITICA',
															'METEO'],
												cols = ['OUT', 'IN', 'MANIPULABLES', 'PROCESOS_IN'],
												force_create=True)
		# print('Nuevas variables: ')
		# print(total_model_dict.keys())
		model_select_menu_new.options = list(total_model_dict.keys())
		model_select_menu_new.value = 'Calidad_Agua'
		models.clear()
		model_plots.children = []
		created_models_checkbox.labels = []
		created_models_checkbox.active = []
	recreate_button.on_click(recreate_callback)

	# Callbacks para los widgets de la interfaz
	def prediction_callback():
		# Llamar al servicio web EDAR_Cartuja_Prediccion con los nuevos parámetros
		model_objective = model_select_menu.value
		model_discretise = 5
		
		# Verificar que el modelo no ha sido creado antes
		if model_objective not in models:		
			json_prediction_document = call_webservice('http://rapidminer.vicomtech.org/api/rest/process/EDAR_Cartuja_Prediccion_JSON?',
														'rapidminer', 'rapidminer', {'Objetivo': model_objective, 'Discretizacion': model_discretise, 'Numero_Atributos': 4},
														out_json=True)

			# TODO Remover anterior y descomentar este cuando Aitor cree los nuevos servicios
			# json_prediction_document = call_webservice(url='http://rapidminer.vicomtech.org/api/rest/process/EDAR_Cartuja_Prediccion_JSON?',
			# 											username='rapidminer',
			# 											password='rapidminer',
			# 											parameters={'Objetivo': model_objective,
			# 														'Discretizacion': model_discretise,
			# 														'Numero_Atributos': 4,
			# 														'Ruta_Periodo': f'/home/admin/EDAR4.0_EDAR_Cartuja_ID_PERIOD_{periodo}.csv',
			# 														'Ruta_Perfilado': '/home/admin/Cartuja_Datos/Perfil_Calidad_out',
			# 														'IN_MODELO': total_model_dict[model_objective]
			# 														},
			# 											out_json=True)	
			
			# Obtener datos
			df_prediction = [json_normalize(data) for data in json_prediction_document]

			decision_tree_df = df_prediction[0]
			confusion_df_raw = df_prediction[1].reindex(columns=list(json_prediction_document[1][0].keys()))
			confusion_df = create_df_confusion(confusion_df_raw)
			weight_df = df_prediction[2]
			pred_df = df_prediction[3]
			slider_df = create_df_sliders(weight_df, pred_df)
			daily_pred_df = pred_df[['timestamp', model_objective, f'prediction({model_objective})']]
			possible_targets = sorted(list(pred_df[model_objective].unique()))
			var_influyentes = list(weight_df['Attribute'])
			decision_tree_data = create_decision_tree_data(decision_tree_df, model_objective)
			
			# Crear nuevos gráficos
			simulate_title = create_div_title(f'Simulación - {model_objective}')
			simulate_title.min_width = 390
			simulate_sliders = DynamicWidget(slider_df, model_objective)
			optimize_wb = DynamicOptimWidget(target=model_objective, possible_targets=possible_targets, var_influyentes=var_influyentes)
			daily_pred_plot = create_daily_pred_plot(daily_pred_df, model_objective)
			decision_tree_plot = create_decision_tree_plot()
			decision_tree_graph = create_decision_tree_graph_renderer(decision_tree_plot, decision_tree_data)
			decision_tree_plot = append_labels_to_decision_tree(decision_tree_plot, decision_tree_graph, decision_tree_data)
			confusion_matrix = create_confusion_matrix(confusion_df)
			weight_plot = create_attribute_weight_plot(weight_df, model_objective)
			corrects_plot = create_corrects_plot(confusion_df, model_objective)
			confusion_title = create_div_title(f'Matriz de confusión - {model_objective}')
			decision_tree_title = create_div_title(f'Arbol de decisión - {model_objective}')
			new_plots = layout([
				[column([simulate_title, simulate_sliders.wb], sizing_mode='stretch_width'), optimize_wb.wb],
				# [column([simulate_title, simulate_sliders.wb], sizing_mode='stretch_width')],
				[daily_pred_plot],
				[column([confusion_title, confusion_matrix], sizing_mode='stretch_width'), weight_plot, corrects_plot],
				[decision_tree_title],
				[decision_tree_plot]
			], name=model_objective, sizing_mode='stretch_width')
			model_plots.children.append(new_plots)
			models.update({model_objective: new_plots})
			models.move_to_end(model_objective, last=False)
			created_models_checkbox.labels = list(models.keys())
			created_models_checkbox.active = list(range(len(models.keys())))
	add_model_button.on_click(prediction_callback)

	def remove_options_handler(new):
		selected_labels = [created_models_checkbox.labels[elements] for elements in created_models_checkbox.active]
		try:
			for element in selected_labels:
				models.pop(element)
				model_plots.children.remove(doc.get_model_by_name(element))
		except:
			for element in selected_labels:
				print(f"El modelo {element} no existe")
		created_models_checkbox.labels = list(models.keys())
		created_models_checkbox.active = list(range(len(models.keys())))
	delete_model_button.on_click(remove_options_handler)

	def show_hide_plots(new):
		selected_labels = [created_models_checkbox.labels[elements] for elements in new]
		# model_plots.children = []
		children = []
		for element in selected_labels:
			children.append(models[element])
		model_plots.children = children
	created_models_checkbox.on_click(show_hide_plots)

	# Creación del layout dinámico de la interfaz
	model_plots = column([])
	prediction_callback()

	# Creación del layout estático de la interfaz
	l = layout([
		[prediction_plot],
		[outlier_plot],
		[simulation_title],
		[model_select_wb, column(created_models_wb, delete_model_button, sizing_mode='stretch_width')],		
		[model_plots]
	], sizing_mode='stretch_both')

	doc.add_root(l)
