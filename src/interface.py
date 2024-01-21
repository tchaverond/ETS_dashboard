import matplotlib
from matplotlib import pyplot as plt
import os
import PySimpleGUI as sg
from webbrowser import open_new_tab

matplotlib.use('TkAgg')

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from src import core


ROOT_PATH = os.getcwd()


class Interface:
    
    def __init__(self, theme='DarkBrown3'):
        self.window = self.make_window(theme)
        self.datafile = None
        self.statistics = None
        self.plots = None
        self.inter_plots = None
        self.figure = None
        self.figure_index = -1
    
    
    def make_window(self, theme):
        
        sg.theme(theme)
        left = sg.Column([
            # TODO: add multiple files
            [sg.FileBrowse("Ajouter un fichier de trajets", target='Input_data'),
             sg.In(key='Input_data', enable_events=True)],
            [sg.Button("Actualiser", key='Run')],
            [sg.Frame("Statistiques :", 
                      [[sg.Multiline(size=(70,20), auto_size_text=True, expand_y=True, 
                                     write_only=True, key='Stats')
                        ]])]
            # TODO: delete existing database
        ])
    
        right = sg.Column([
            [sg.Canvas(size=(500, 500), key='Canvas')],
            [sg.Button("Graphique précédent", disabled=True, key='Previous'),
             sg.Button("Graphique suivant", disabled=True, key='Next')],
            [sg.Button("Carte interactive des villes", disabled=True, key='Inter_cities'),
             sg.Button("Carte interactive des trajets", disabled=True, key='Inter_routes')]
        ])
        
        layout = [[left, right]]
        window = sg.Window("Euro Truck Simulator Statistiques et Visualisation", 
                           layout, grab_anywhere=True, resizable=True)
        return window
    
    
    def draw_figure(self, canvas):
        self.figure = FigureCanvasTkAgg(self.plots[self.figure_index], canvas)
        self.figure.draw()
        self.figure.get_tk_widget().pack(side='top', fill='both', expand=1)

    def delete_figure(self):
        self.figure.get_tk_widget().forget()
        plt.close('all')
    
    def show_current_figure(self):
        if self.figure is not None:
            self.delete_figure()
        self.draw_figure(self.window['Canvas'].TKCanvas)
        
    def show_statistics(self):
        self.window['Stats'].update(
            '\n'.join([' : '.join([k,v]) for k,v in self.statistics.items()]))


    def run(self):
        
        while True:
            event, values = self.window.read()
            if event == sg.WIN_CLOSED:
                break
            
            if event == 'Input_data':
                self.datafile = values['Input_data']
            
            if event == 'Run':
                for obj_name in ['Previous', 'Next', 'Inter_cities', 'Inter_routes']:                
                    self.window[obj_name].update(disabled=False)
                self.statistics, self.plots, self.inter_plots = core.run(
                    self.datafile)
                self.show_statistics()
                self.figure_index = 0
                self.show_current_figure()

            if event == 'Previous':
                self.figure_index -= 1
                if self.figure_index < 0:
                    self.figure_index = 0
                else:
                    self.show_current_figure()
            
            if event == 'Next':
                self.figure_index += 1
                if self.figure_index > len(self.plots) - 1:
                    self.figure_index = len(self.plots) - 1
                else:
                    self.show_current_figure()
            
            if event == 'Inter_cities':
                if os.path.exists("data/"):
                    url = "data/cities.html"
                else:
                    url = "_internal/data/cities.html"
                self.inter_plots[0].save(url)
                open_new_tab('/'.join([ROOT_PATH, url]))
            
            if event == 'Inter_routes':
                if os.path.exists("data/"):
                    url = "data/routes.html"
                else:
                    url = "_internal/data/routes.html"
                self.inter_plots[1].save(url)
                open_new_tab('/'.join([ROOT_PATH, url]))
        
        self.window.close()


if __name__ == "__main__":
    interface = Interface()
    interface.run()
