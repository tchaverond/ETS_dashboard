import matplotlib
from matplotlib import pyplot as plt
import PySimpleGUI as sg

matplotlib.use('TkAgg')

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from src import core


class Interface:
    
    def __init__(self, theme='DarkBrown3'):
        self.window = self.make_window(theme)
        self.datafile = None
        self.statistics = None
        self.plots = None
        self.figure = None
        self.figure_index = -1
    
    
    def make_window(self, theme):
        
        sg.theme(theme)
        left = sg.Column([
            [sg.FileBrowse("Ajouter un fichier de trajets", target='Input_data'),
             sg.In(key='Input_data', enable_events=True)],
            [sg.Button("Actualiser", key='Run')],
            [sg.Frame("Statistiques :", 
                      [[sg.Multiline(size=(70,20), auto_size_text=True, expand_y=True, 
                                     write_only=True, key='Stats')
                        ]])]
        ])
    
        right = sg.Column([
            [sg.Canvas(size=(500, 500), key='Canvas')],
            [sg.Button("Graphique précédent", disabled=True, key='Previous'),
             sg.Button("Graphique suivant", disabled=True, key='Next')]
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
                self.window['Previous'].update(disabled=False)
                self.window['Next'].update(disabled=False)
                self.statistics, self.plots = core.run(
                    self.datafile)
                self.show_statistics()
                self.figure_index = 0
                self.show_current_figure()

            if event == 'Previous':
                self.figure_index -= 1
                if self.figure_index < 0:
                    self.figure_index = 0
                else:
                    self.show_individual_result()
            
            if event == 'Next':
                self.figure_index += 1
                if self.figure_index > len(self.plots) - 1:
                    self.figure_index = len(self.plots) - 1
                else:
                    self.show_individual_result()
        
        self.window.close()


if __name__ == "__main__":
    interface = Interface()
    interface.run()
