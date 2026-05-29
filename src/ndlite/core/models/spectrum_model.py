class SpectrumModel:
    def __init__(self, file_path, dic, data, color_pos, color_neg):
        self.file_path = file_path
        self.dic = dic
        self.raw_data = data
        self.color_pos = color_pos
        self.color_neg = color_neg
        self.enabled = True
        self.peaks_enabled = True
        self.baseline_correction = None

        # Determine dimensionality
        self.ndim = data.ndim
        order = dic.get('FDDIMORDER', [2, 1, 3, 4])
        self.is_1d = (self.ndim == 1)

        # Coordinate axes
        if self.ndim == 1:
            orig_dim_x = int(order[0]) if len(order) > 0 else 2
            self.label_x = dic.get(f'FDF{orig_dim_x}LABEL', '1H')
            self.label_y = "Intensity"
            self.label_z = None
            self.x_dim, self.y_dim, self.z_dim = 0, None, None
            self.nz = 1
        elif self.ndim == 3:
            self.z_dim, self.y_dim, self.x_dim = 0, 1, 2
            orig_dim_x = int(order[0]) if len(order) > 0 else 2
            orig_dim_y = int(order[1]) if len(order) > 1 else 3
            orig_dim_z = int(order[2]) if len(order) > 2 else 1
            self.label_x = dic.get(f'FDF{orig_dim_x}LABEL', 'X')
            self.label_y = dic.get(f'FDF{orig_dim_y}LABEL', 'Y')
            self.label_z = dic.get(f'FDF{orig_dim_z}LABEL', 'Z')
            self.nz = data.shape[self.z_dim]
        else:
            self.y_dim, self.x_dim = 0, 1
            orig_dim_x = int(order[0]) if len(order) > 0 else 2
            orig_dim_y = int(order[1]) if len(order) > 1 else 1
            self.label_x = dic.get(f'FDF{orig_dim_x}LABEL', 'X')
            self.label_y = dic.get(f'FDF{orig_dim_y}LABEL', 'Y')
            self.label_z = None
            self.z_dim = None
            self.nz = 1
