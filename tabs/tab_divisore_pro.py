import flet as ft
from utils.styles import AppStyles, AppColors, PageConstants
import urllib.parse

class DivisoreProTab(ft.Container):
    def __init__(self, controller, show_back_button=False):
        super().__init__(padding=PageConstants.PAGE_PADDING, expand=True) # Usa padding standard
        self.controller = controller
        
        # Stato locale
        self.expenses = []
        self.final_message = ""
        
        # --- UI Components ---
        
        # Header
        self.txt_header = AppStyles.title_text("⚖️ Divisore Pro")
        # removed version text
        
        # Nuova Spesa Card
        self.tf_name = ft.TextField(label="Chi ha pagato?", expand=2)
        self.tf_amount = ft.TextField(label="€ Importo", expand=1, keyboard_type=ft.KeyboardType.NUMBER)
        self.tf_shares = ft.TextField(label="N° Pers", value="1", expand=1, keyboard_type=ft.KeyboardType.NUMBER)
        
        self.btn_add = ft.ElevatedButton(
            text="Aggiungi alla lista",
            on_click=self._add_expense,
            style=ft.ButtonStyle(
                color=ft.Colors.WHITE,
                bgcolor=AppColors.PRIMARY,
                shape=ft.RoundedRectangleBorder(radius=12),
                padding=16
            ),
            width=400 # Max width for button
        )
        
        card_nuova_spesa = AppStyles.card_container(
            content=ft.Column([
                AppStyles.subheader_text("Nuova Spesa"),
                ft.ResponsiveRow([
                    ft.Column([self.tf_name], col={"xs": 12, "sm": 6}),
                    ft.Column([self.tf_amount], col={"xs": 6, "sm": 3}),
                    ft.Column([self.tf_shares], col={"xs": 6, "sm": 3}),
                ]),
                ft.Container(content=self.btn_add, alignment=ft.alignment.center)
            ], spacing=20),
            padding=20
        )
        
        # Lista Partecipanti Card
        self.lv_expenses = ft.ListView(spacing=10, padding=0, auto_scroll=False)
        self.txt_no_data = ft.Text("Nessun dato inserito", color=AppColors.TEXT_SECONDARY, size=14, text_align=ft.TextAlign.CENTER)
        
        self.txt_total_money = ft.Text("€ 0.00", weight=ft.FontWeight.BOLD)
        self.txt_total_shares = ft.Text("0", weight=ft.FontWeight.BOLD)
        
        summary_info = ft.Container(
            content=ft.Row([
                ft.Row([ft.Text("Totale: ", color=AppColors.TEXT_SECONDARY), self.txt_total_money]),
                ft.Row([ft.Text("Quote: ", color=AppColors.TEXT_SECONDARY), self.txt_total_shares]),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            padding=ft.padding.only(top=12),
            border=ft.border.only(top=ft.BorderSide(1, "#f1f5f9"))
        )
        
        card_lista = AppStyles.card_container(
            content=ft.Column([
                AppStyles.subheader_text("Lista Partecipanti"),
                ft.Container(
                    content=ft.Column([
                        self.txt_no_data,
                        self.lv_expenses
                    ]),
                    height=200, # Fixed height for list or flexible? Let's try flexible in container if needed
                ),
                summary_info
            ]),
            padding=20
        )

        # Azioni e Risultati
        self.btn_calc = ft.ElevatedButton(
            text="💰 Calcola i Debiti",
            on_click=self._calculate_debts,
            style=ft.ButtonStyle(
                color=ft.Colors.WHITE,
                bgcolor=AppColors.SUCCESS, # Greenish if available, else primary
                shape=ft.RoundedRectangleBorder(radius=12),
                padding=16
            ),
             width=400
        )
        
        self.btn_wa = ft.ElevatedButton(
            text="📱 Invia su WhatsApp",
            on_click=self._share_whatsapp,
            style=ft.ButtonStyle(
                color=ft.Colors.WHITE,
                bgcolor="#25d366", # WhatsApp Color
                shape=ft.RoundedRectangleBorder(radius=12),
                padding=16
            ),
             width=400,
             visible=False
        )

        self.btn_reset = ft.TextButton(
            text="🗑️ Ricomincia da zero",
            on_click=self._reset_all,
            style=ft.ButtonStyle(
                color=ft.Colors.RED,
            )
        )
        
        # Sezione Risultati (inizialmente nascosta)
        self.results_content = ft.Column(spacing=10)
        self.card_results = AppStyles.card_container(
            content=ft.Column([
                ft.Text("💸 Risultato:", size=18, weight=ft.FontWeight.BOLD, color=AppColors.SUCCESS),
                self.results_content
            ]),
            padding=20
        )
        self.card_results.visible = False
        
        self.footer = ft.Container(
             content=ft.Text("By Iscavar", size=12, color=AppColors.TEXT_SECONDARY, text_align=ft.TextAlign.RIGHT),
             padding=ft.padding.only(top=40, bottom=20),
             alignment=ft.alignment.center_right
        )

        # Back to Login Button (only for public view)
        self.btn_back = None
        if show_back_button:
            self.btn_back = ft.TextButton(
                "← Torna al Login",
                icon=ft.Icons.ARROW_BACK,
                on_click=lambda _: self.page.go("/"),
                style=ft.ButtonStyle(color=AppColors.PRIMARY)
            )

        # Layout Main
        header_content = [self.txt_header]
        if self.btn_back:
            header_content.insert(0, self.btn_back)

        self.content = ft.Column(
            [
                ft.Container(
                    content=ft.Row(
                        [self.btn_back, self.txt_header] if self.btn_back else [self.txt_header],
                        alignment=ft.MainAxisAlignment.START if self.btn_back else ft.MainAxisAlignment.CENTER
                    ),
                    alignment=ft.alignment.center
                ),
                card_nuova_spesa,
                card_lista,
                ft.Container(content=ft.Column([self.btn_calc, self.btn_wa], spacing=10), alignment=ft.alignment.center),
                self.card_results,
                ft.Container(content=self.btn_reset, alignment=ft.alignment.center),
                self.footer
            ],
            scroll=ft.ScrollMode.HIDDEN # Scroll handled by parent or page
        )

    def update_view_data(self, is_initial_load=False):
        pass # No external data needed

    def _add_expense(self, e):
        name = self.tf_name.value.strip() if self.tf_name.value else ""
        try:
            amount = float(self.tf_amount.value.replace(',', '.')) if self.tf_amount.value else 0.0
        except ValueError:
            amount = 0.0
            
        try:
            shares = int(self.tf_shares.value) if self.tf_shares.value else 1
        except ValueError:
            shares = 1
            
        if not name or amount <= 0:
            self.controller.show_snack_bar("Inserisci nome e importo valido.", False)
            return
        
        if shares < 1: shares = 1
        
        # Check existing
        existing = next((x for x in self.expenses if x['name'].lower() == name.lower()), None)
        if existing:
            existing['amount'] += amount
            existing['shares'] += shares
        else:
            self.expenses.append({'name': name, 'amount': amount, 'shares': shares})
            
        # Reset inputs
        self.tf_name.value = ""
        self.tf_amount.value = ""
        self.tf_shares.value = "1"
        self.tf_name.focus()
        
        self._render_list()
        self._hide_results()
        self.update()

    def _render_list(self):
        self.lv_expenses.controls.clear()
        total_money = 0.0
        total_shares = 0
        
        if not self.expenses:
            self.txt_no_data.visible = True
        else:
            self.txt_no_data.visible = False
            for exp in self.expenses:
                total_money += exp['amount']
                total_shares += exp['shares']
                
                row = ft.Container(
                    content=ft.Row([
                        ft.Row([
                            ft.Text(exp['name'], weight=ft.FontWeight.BOLD),
                            ft.Container(
                                content=ft.Text(f"x{exp['shares']}", size=12, color=AppColors.PRIMARY, weight=ft.FontWeight.BOLD),
                                bgcolor="#dbeafe", # Light blue
                                border_radius=12,
                                padding=ft.padding.symmetric(horizontal=8, vertical=2)
                            )
                        ], spacing=6),
                        ft.Text(f"€ {exp['amount']:.2f}")
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    padding=ft.padding.symmetric(vertical=12),
                    border=ft.border.only(bottom=ft.BorderSide(1, "#f1f5f9"))
                )
                self.lv_expenses.controls.append(row)
                
        self.txt_total_money.value = f"€ {total_money:.2f}"
        self.txt_total_shares.value = str(total_shares)

    def _calculate_debts(self, e):
        if len(self.expenses) < 2:
             self.controller.show_snack_bar("Inserisci almeno due persone per calcolare.", False)
             return

        total_money = sum(x['amount'] for x in self.expenses)
        total_shares = sum(x['shares'] for x in self.expenses)
        share_price = total_money / total_shares if total_shares > 0 else 0
        
        # Deep copy for calculation to not mess up inputs if specific logic requires it, 
        # but here we calculate balances on the fly.
        
        balances = []
        for p in self.expenses:
            bal = p['amount'] - (p['shares'] * share_price)
            balances.append({'name': p['name'], 'balance': bal})
            
        debtors = sorted([b for b in balances if b['balance'] < -0.01], key=lambda x: x['balance'])
        creditors = sorted([b for b in balances if b['balance'] > 0.01], key=lambda x: x['balance'], reverse=True)
        
        self.results_content.controls.clear()
        
        # Header info
        self.results_content.controls.append(
            ft.Text(f"Quota per persona: € {share_price:.2f}", weight=ft.FontWeight.BOLD, color=AppColors.TEXT_SECONDARY)
        )
        
        # WhatsApp Message construction
        self.final_message = "*💰 Divisore Pro - v.0.03*\n\n"
        self.final_message += f"• Totale: € {total_money:.2f}\n"
        self.final_message += f"• Quota a testa: € {share_price:.2f}\n\n"
        self.final_message += "*Debiti da saldare:*\n"
        
        transactions_text = ""
        
        i = 0
        j = 0
        while i < len(debtors) and j < len(creditors):
            amount = min(abs(debtors[i]['balance']), creditors[j]['balance'])
            row_text = f"{debtors[i]['name']} dà € {amount:.2f} a {creditors[j]['name']}"
            
            # UI Row
            res_item = ft.Container(
                content=ft.Text(row_text, size=15),
                bgcolor="#f0fdf4", # Light green
                border_radius=10,
                padding=12,
                border=ft.border.only(left=ft.BorderSide(4, AppColors.SUCCESS))
            )
            self.results_content.controls.append(res_item)
            
            transactions_text += f"– {row_text}\n"
            
            debtors[i]['balance'] += amount
            creditors[j]['balance'] -= amount
            
            if abs(debtors[i]['balance']) < 0.01: i += 1
            if creditors[j]['balance'] < 0.01: j += 1
            
        if not transactions_text:
            transactions_text = "Tutti in pari!"
            self.results_content.controls.append(ft.Text("Conti già in pari!"))
            
        self.final_message += transactions_text
        
        self.card_results.visible = True
        self.btn_wa.visible = True
        self.update()
        
        # Scroll to bottom to show results (if page supports it)
        # In Flet web scroll_to might need the key handling, or assuming user scrolls.
        
    def _share_whatsapp(self, e):
        url = f"https://wa.me/?text={urllib.parse.quote(self.final_message)}"
        self.page.launch_url(url)
        
    def _hide_results(self):
        self.card_results.visible = False
        self.btn_wa.visible = False
        
    def _reset_all(self, e):
        # We need a confirm dialog. Using controller's dialog if possible or a simple one.
        # For simplicity in this bespoke tab, let's use the controller's generic confirm or create a small one.
        # But `confirm_delete_dialog` has specific text. 
        # Let's just reset directly or use a simple snackbar based approach? 
        # The user asked for "Confirm".
        
        def on_confirm_reset():
            self.expenses = []
            self._render_list()
            self._hide_results()
            self.tf_name.value = ""
            self.tf_amount.value = ""
            self.tf_shares.value = "1"
            self.update()
            
        # Creating a one-off dialog for this tab
        dlg = ft.AlertDialog(
            title=ft.Text("Conferma Reset"),
            content=ft.Text("Sei sicuro di voler cancellare tutto?"),
            actions=[
                ft.TextButton("Sì", on_click=lambda _: [self.page.close_dialog(), on_confirm_reset()]),
                ft.TextButton("No", on_click=lambda _: self.page.close_dialog()),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.show_dialog(dlg)

