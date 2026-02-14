import flet as ft
import logging

logger = logging.getLogger("OnboardingDialog")

class OnboardingDialog(ft.AlertDialog):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.loc = controller.loc
        self.modal = True
        
        self.current_step = 1
        
        # UI Elements
        self.title = ft.Text("", size=20, weight=ft.FontWeight.BOLD)
        self.content_text = ft.Text("")
        self.image = ft.Image(src="", width=200, height=150, fit=ft.ImageFit.CONTAIN, visible=False)
        
        self.btn_next = ft.ElevatedButton(text="Avanti", on_click=self._next_step)
        self.btn_prev = ft.TextButton(text="Indietro", on_click=self._prev_step, visible=False)
        self.btn_skip = ft.TextButton(text="Salta Tutorial", on_click=self._skip_tutorial, color=ft.Colors.GREY_400)
        
        self.content = ft.Column([
            self.image,
            self.content_text,
        ], tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        
        self.actions = [
            self.btn_skip,
            self.btn_prev,
            self.btn_next
        ]
        self.actions_alignment = ft.MainAxisAlignment.END

    def show(self):
        self.current_step = 1
        self._update_ui()
        self.open = True
        if self not in self.controller.page.overlay:
            self.controller.page.overlay.append(self)
        self.controller.page.update()

    def _update_ui(self):
        self.btn_prev.visible = self.current_step > 1
        
        if self.current_step == 1:
            self.title.value = "Benvenuto in BudgetAmico! 🚀"
            self.content_text.value = "Questa guida ti aiuterà a configurare i tuoi primi strumenti finanziari in pochi secondi."
            self.btn_next.text = "Iniziamo!"
            self.image.visible = False
            
        elif self.current_step == 2:
            self.title.value = "Passo 1: Il tuo primo Conto 🏦"
            self.content_text.value = "I conti sono il cuore dell'app. Crea un conto (es. 'Contanti', 'Banca') per iniziare a tracciare le tue spese."
            self.btn_next.text = "Crea il mio primo Conto"
            
        elif self.current_step == 3:
            self.title.value = "Passo 2: Carte di Credito o Debito 💳"
            self.content_text.value = "Hai una carta prepagata o di credito? Aggiungila per gestire i plafond e le scadenze mensili."
            self.btn_next.text = "Aggiungi una Carta"
            self.btn_skip.text = "Forse più tardi"
            
        elif self.current_step == 4:
            self.title.value = "Tutto pronto! 🎉"
            self.content_text.value = "Ora puoi iniziare ad aggiungere le tue prime transazioni dalla Home."
            self.btn_next.text = "Chiudi e Inizia"
            self.btn_skip.visible = False
            
        self.controller.page.update()

    def _next_step(self, e):
        if self.current_step == 1:
            self.current_step = 2
            self._update_ui()
        elif self.current_step == 2:
            # Open Account Dialog
            self.open = False
            self.controller.page.update()
            self.current_step = 3
            self.controller.open_new_account_dialog()
            # The controller should call back or we wait?
            # For simplicity, we'll re-open after dialog closes if we can hook it.
            # but usually, we just go to the next step.
            self.show_next_automatic()
        elif self.current_step == 3:
            # Open Card Dialog
            self.open = False
            self.controller.page.update()
            self.current_step = 4
            self.controller.open_new_card_dialog()
            self.show_next_automatic()
        elif self.current_step == 4:
            self._finish()

    def _prev_step(self, e):
        if self.current_step > 1:
            self.current_step -= 1
            self._update_ui()

    def show_next_automatic(self):
        """Called by controller to show next step after an operation."""
        # Wait a bit for the UI to settle
        import time
        time.sleep(0.5)
        self.show_direct(self.current_step)

    def show_direct(self, step):
        self.current_step = step
        self._update_ui()
        self.open = True
        self.controller.page.update()

    def _skip_tutorial(self, e):
        self._finish()

    def _finish(self):
        self.open = False
        from db.gestione_config import set_onboarding_completed
        set_onboarding_completed(self.controller.get_family_id())
        self.controller.page.update()
        self.controller.show_snack_bar("Tutorial completato! Buona gestione!", success=True)
