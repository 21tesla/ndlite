from PyQt6.QtGui import QAction

class MenuBuilder:
    def __init__(self, main_window):
        self.mw = main_window

    def build(self):
        menubar = self.mw.menuBar()
        menubar.setNativeMenuBar(True)

        # Shared Actions
        save_peaks_action = QAction("Save Peaks", self.mw)
        save_peaks_action.setShortcut("s")
        save_peaks_action.triggered.connect(self.mw.peak_controller.save_peaks)

        auto_pick_action = QAction("Auto Pick", self.mw)
        auto_pick_action.triggered.connect(self.mw.peak_controller.auto_pick)

        show_peaks_action = QAction("Show Peaks", self.mw)
        show_peaks_action.setShortcut("Shift+S")
        show_peaks_action.triggered.connect(self.mw.peak_controller.show_peaks)
        
        hide_peaks_action = QAction("Hide Peaks", self.mw)
        hide_peaks_action.setShortcut("Shift+H")
        hide_peaks_action.triggered.connect(self.mw.peak_controller.hide_peaks)

        clear_peaks_action = QAction("Clear All Peaks", self.mw)
        clear_peaks_action.triggered.connect(self.mw.peak_controller.clear_peaks)
         
        renumber_peaks_action = QAction("Renumber Peaks", self.mw)
        renumber_peaks_action.setShortcut("Shift+R")
        renumber_peaks_action.triggered.connect(self.mw.peak_controller.renumber_peaks)

        pick_peaks_action = QAction("Pick Peaks", self.mw)
        pick_peaks_action.setShortcut("p")
        pick_peaks_action.triggered.connect(lambda: self.mw.set_mode('peak_pick'))

        force_pick_action = QAction("Force Pick", self.mw)
        force_pick_action.setShortcut("Shift+P")
        force_pick_action.triggered.connect(self.mw.peak_controller.force_pick)

        # --- File Menu ---
        file_menu = menubar.addMenu("File")
        
        load_action = QAction("Load File(s)...", self.mw)
        load_action.setShortcut("Ctrl+O")
        load_action.triggered.connect(self.mw.io_controller.load_file_dialog)
        file_menu.addAction(load_action)

        file_menu.addSeparator()
        
        settings_action = QAction("Settings...", self.mw)
        settings_action.triggered.connect(self.mw.io_controller.open_settings_dialog)
        file_menu.addAction(settings_action)
        
        file_menu.addSeparator()
        
        file_menu.addAction(save_peaks_action)
        
        export_menu = file_menu.addMenu("Export")
        
        export_spectrum_action = QAction("Spectrum", self.mw)
        export_spectrum_action.triggered.connect(self.mw.exporter.export_spectrum)
        export_menu.addAction(export_spectrum_action)
        
        export_peaks_action = QAction("Peaks + Spectrum", self.mw)
        export_peaks_action.triggered.connect(self.mw.exporter.export_peaks_spectrum)
        export_menu.addAction(export_peaks_action)

        file_menu.addSeparator()

        quit_action = QAction("Quit", self.mw)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.mw.close)
        file_menu.addAction(quit_action)
        
        # --- 1D Mode Menu ---
        self.mw.one_d_menu = menubar.addMenu("1D-Mode")
        
        baseline_menu = self.mw.one_d_menu.addMenu("Baseline")
        
        als_action = QAction("Auto-Correct Baseline (ALS)", self.mw)
        als_action.triggered.connect(self.mw.baseline_controller.run_als_baseline)
        baseline_menu.addAction(als_action)
        
        interactive_base_action = QAction("Interactive Anchors", self.mw)
        interactive_base_action.triggered.connect(self.mw.baseline_controller.start_interactive_baseline)
        baseline_menu.addAction(interactive_base_action)
        
        clear_base_action = QAction("Clear Baseline", self.mw)
        clear_base_action.triggered.connect(self.mw.baseline_controller.clear_baseline)
        baseline_menu.addAction(clear_base_action)        

        self.mw.one_d_menu.addSeparator()

        self.mw.one_d_menu.addAction(auto_pick_action)
        self.mw.one_d_menu.addAction(pick_peaks_action)
        self.mw.one_d_menu.addAction(force_pick_action)

        self.mw.one_d_menu.addSeparator()

        peak_funcs_menu = self.mw.one_d_menu.addMenu("Peak functions")
        peak_funcs_menu.addAction(show_peaks_action)
        peak_funcs_menu.addAction(hide_peaks_action)
        peak_funcs_menu.addAction(clear_peaks_action)
        peak_funcs_menu.addAction(renumber_peaks_action)

        self.mw.one_d_menu.addSeparator()

        fit_menu = self.mw.one_d_menu.addMenu("Fitting")
        
        fit_lor_action = QAction("Lorentzian", self.mw)
        fit_lor_action.triggered.connect(lambda: self.mw.fitting_controller.fit_1d_peaks('lorentzian'))
        fit_menu.addAction(fit_lor_action)
        
        fit_gau_action = QAction("Gaussian", self.mw)
        fit_gau_action.triggered.connect(lambda: self.mw.fitting_controller.fit_1d_peaks('gaussian'))
        fit_menu.addAction(fit_gau_action)
        
        fit_pvo_action = QAction("Pseudo-Voigt", self.mw)
        fit_pvo_action.triggered.connect(lambda: self.mw.fitting_controller.fit_1d_peaks('pseudo_voigt'))
        fit_menu.addAction(fit_pvo_action)

        fit_menu.addSeparator()

        clear_fits_action = QAction("Clear Fits", self.mw)
        clear_fits_action.triggered.connect(self.mw.fitting_controller.clear_1d_fits)
        fit_menu.addAction(clear_fits_action)

        self.mw.one_d_menu.addSeparator()

        self.mw.one_d_menu.addAction(save_peaks_action)


        # --- 2D/3D-Peaks Menu ---
        self.mw.two_d_menu = menubar.addMenu("2D/3D-Mode")
        
        self.mw.two_d_menu.addAction(auto_pick_action)
        self.mw.two_d_menu.addAction(pick_peaks_action)
        self.mw.two_d_menu.addAction(force_pick_action)

        self.mw.two_d_menu.addAction(show_peaks_action)
        self.mw.two_d_menu.addAction(hide_peaks_action)
        
        delete_peaks_action = QAction("Delete Peaks", self.mw)
        delete_peaks_action.setShortcut("d")
        delete_peaks_action.triggered.connect(lambda: self.mw.set_mode('peak_delete'))
        self.mw.two_d_menu.addAction(delete_peaks_action)
        
        self.mw.two_d_menu.addAction(clear_peaks_action)
        self.mw.two_d_menu.addAction(renumber_peaks_action)
        self.mw.two_d_menu.addAction(save_peaks_action)
                
 
        # --- Extras Menu ---
        extras_menu = menubar.addMenu("Extras")
        
        update_action = QAction("Check for Updates...", self.mw)
        update_action.triggered.connect(self.mw.updater.check_for_updates)
        extras_menu.addAction(update_action)
        
        help_action = QAction("Help", self.mw)
        help_action.setShortcut("h")
        help_action.triggered.connect(self.mw.show_help_dialog)
        extras_menu.addAction(help_action)
