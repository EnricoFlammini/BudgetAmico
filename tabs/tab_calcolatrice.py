import flet as ft
from utils.styles import AppStyles, AppColors, PageConstants

class CalcolatriceTab(ft.Container):
    def __init__(self, controller):
        super().__init__(padding=PageConstants.PAGE_PADDING, expand=True)
        self.controller = controller
        
        self.rows = []
        self.rows_container = ft.Column(scroll=ft.ScrollMode.ADAPTIVE, expand=True)
        
        # Totals
        self.txt_totale = AppStyles.big_currency_text("€ 0,00", color=AppColors.PRIMARY)
        
        # Add initial rows
        for _ in range(10):
            self._add_row()
            
        self.content = ft.Column([
            ft.Row([
                AppStyles.title_text("Foglio di Calcolo"),
                ft.Row([
                    ft.IconButton(ft.Icons.ADD, tooltip="Aggiungi Riga", on_click=self._on_add_click),
                    ft.IconButton(ft.Icons.CLEAR_ALL, tooltip="Pulisci Tutto", on_click=self._clear_all)
                ])
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            
            ft.Container(
                content=ft.Row([
                    ft.Text("Descrizione", weight=ft.FontWeight.BOLD, expand=2),
                    ft.Text("Formula / Valore", weight=ft.FontWeight.BOLD, expand=1),
                    ft.Text("Risultato", weight=ft.FontWeight.BOLD, width=100, text_align=ft.TextAlign.RIGHT),
                    ft.Container(width=40) # Space for delete icon
                ]),
                padding=ft.padding.only(bottom=5),
                border=ft.border.only(bottom=ft.BorderSide(1, ft.Colors.OUTLINE))
            ),
            
            self.rows_container,
            
            ft.Container(height=20),
            ft.Divider(),
            ft.Row([
                AppStyles.subheader_text("Totale:"),
                self.txt_totale
            ], alignment=ft.MainAxisAlignment.END, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        ])

    def _on_add_click(self, e):
        self._add_row(update=True)

    def _add_row(self, update=False):
        row_control = CalculatorRow(self._on_row_update, self._delete_row)
        self.rows.append(row_control)
        self.rows_container.controls.append(row_control)
        if update:
            self.rows_container.update()
            if self.page: self.page.update()

    def _delete_row(self, row_instance):
        if row_instance in self.rows:
            self.rows.remove(row_instance)
            self.rows_container.controls.remove(row_instance)
            self._update_total()
            self.rows_container.update()

    def _clear_all(self, e):
        self.rows.clear()
        self.rows_container.controls.clear()
        for _ in range(5): self._add_row()
        self._update_total()
        if self.page: self.page.update()

    def _on_row_update(self):
        self._update_total()

    def _update_total(self):
        total = sum(row.get_value() for row in self.rows)
        self.txt_totale.value = self.controller.loc.format_currency(total)
        if self.page: self.txt_totale.update()
        
    def update_view_data(self):
        pass

class CalculatorRow(ft.Container):
    def __init__(self, update_callback, delete_callback):
        super().__init__(padding=5)
        self.update_callback = update_callback
        self.delete_callback = delete_callback
        self.value = 0.0
        
        self.tf_desc = ft.TextField(
            border=ft.InputBorder.NONE, 
            hint_text="Voce...", 
            text_size=14,
            expand=2
        )

        self.tf_formula = ft.TextField(
            border=ft.InputBorder.OUTLINE, 
            hint_text="0", 
            text_size=14,
            expand=1,
            content_padding=10,
            on_blur=self._evaluate,
            on_submit=self._evaluate
        )
        self.txt_result = ft.Text("0.00", width=100, text_align=ft.TextAlign.RIGHT, weight=ft.FontWeight.BOLD)
        
        self.content = ft.Row([
            self.tf_desc,
            ft.Container(width=10),
            self.tf_formula,
            self.txt_result,
            ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color=ft.Colors.RED_400, on_click=lambda e: self.delete_callback(self))
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER)
        
        # Add bottom border
        self.border = ft.border.only(bottom=ft.BorderSide(0.5, ft.Colors.OUTLINE_VARIANT))

    def _evaluate(self, e):
        formula = self.tf_formula.value
        if not formula:
            self.value = 0.0
            self.txt_result.value = "0.00"
        else:
            try:
                # Replace comma with dot
                formula = formula.replace(",", ".")
                # Safe eval: limits available names (none)
                # Note: 'eval' is generally unsafe, but for a local desktop app calc it's acceptable if limited.
                # Just restricting globals/locals.
                result = eval(formula, {"__builtins__": None}, {})
                if isinstance(result, (int, float)):
                    self.value = float(result)
                    self.txt_result.value = f"{self.value:,.2f}"
                    self.txt_result.color = None
                else:
                    self.value = 0.0
                    self.txt_result.value = "Err"
                    self.txt_result.color = ft.Colors.ERROR
            except:
                self.value = 0.0
                self.txt_result.value = "Err"
                self.txt_result.color = ft.Colors.ERROR
        
        self.txt_result.update()
        self.update_callback()

    def get_value(self):
        return self.value
