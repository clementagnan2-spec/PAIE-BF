# -*- coding: utf-8 -*-
"""
main.py
-------
Application de traitement de la paie mensuelle -- Burkina Faso.

Deux niveaux d'accès :
  - Administrateur : mot de passe fixe (modifiable), accès aux paramètres
    de paie et au mot de passe Utilisateur.
  - Utilisateur : mot de passe qui change automatiquement chaque mois,
    accès à la saisie des employés et au calcul de la paie.

Lancer avec :  python main.py
"""

import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import auth
import storage
from payroll_engine import Employee, compute_payslip, DEFAULT_PARAMS

APP_TITLE = "Paie Burkina — Traitement des salaires mensuels"
PAID_SOFTWARE_NOTICE = "⚠ Ce logiciel est payant. Toute utilisation non autorisée est interdite."

MOIS_FR = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet",
           "Août", "Septembre", "Octobre", "Novembre", "Décembre"]


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1100x680")
        self.minsize(950, 600)

        self.config_data = storage.load()
        self.role = None  # "admin" ou "user"

        self.container = ttk.Frame(self)
        self.container.pack(fill="both", expand=True)

        self.show_login()

    # ------------------------------------------------------------------
    def clear(self):
        for w in self.container.winfo_children():
            w.destroy()

    def show_login(self):
        self.role = None
        self.clear()
        LoginScreen(self.container, self)

    def show_main(self):
        self.clear()
        MainScreen(self.container, self)


# ==========================================================================
# ÉCRAN DE CONNEXION
# ==========================================================================

class LoginScreen(ttk.Frame):
    def __init__(self, parent, app: App):
        super().__init__(parent)
        self.app = app
        self.pack(fill="both", expand=True)

        banner = tk.Label(self, text=PAID_SOFTWARE_NOTICE, fg="white", bg="#b8860b",
                           font=("Segoe UI", 10, "bold"), pady=8)
        banner.pack(fill="x", side="top")

        center = ttk.Frame(self)
        center.pack(expand=True)

        ttk.Label(center, text="Paie Burkina", font=("Segoe UI", 22, "bold")).pack(pady=(40, 4))
        ttk.Label(center, text="Traitement des salaires mensuels",
                  font=("Segoe UI", 11)).pack(pady=(0, 24))

        form = ttk.Frame(center)
        form.pack()

        ttk.Label(form, text="Rôle :").grid(row=0, column=0, sticky="e", padx=6, pady=6)
        self.role_var = tk.StringVar(value="Utilisateur")
        role_combo = ttk.Combobox(form, textvariable=self.role_var,
                                   values=["Utilisateur", "Administrateur"],
                                   state="readonly", width=20)
        role_combo.grid(row=0, column=1, sticky="w", padx=6, pady=6)

        ttk.Label(form, text="Mot de passe :").grid(row=1, column=0, sticky="e", padx=6, pady=6)
        self.pwd_var = tk.StringVar()
        pwd_entry = ttk.Entry(form, textvariable=self.pwd_var, show="•", width=23)
        pwd_entry.grid(row=1, column=1, sticky="w", padx=6, pady=6)
        pwd_entry.bind("<Return>", lambda e: self.try_login())
        pwd_entry.focus_set()

        ttk.Button(center, text="Se connecter", command=self.try_login).pack(pady=16)

        info = ttk.Label(
            center,
            text="Le mot de passe Utilisateur change automatiquement chaque\n"
                 "début de mois. Contactez l'administrateur pour l'obtenir.",
            justify="center", foreground="#555")
        info.pack(pady=(6, 0))

        footer = tk.Label(self, text=PAID_SOFTWARE_NOTICE, fg="#b8860b",
                           font=("Segoe UI", 8, "italic"))
        footer.pack(side="bottom", pady=6)

    def try_login(self):
        role = self.role_var.get()
        pwd = self.pwd_var.get().strip()
        cfg = self.app.config_data

        if role == "Administrateur":
            ok = auth.verify_password(pwd, cfg["admin_salt"], cfg["admin_hash"])
            if ok:
                self.app.role = "admin"
                self.app.show_main()
            else:
                messagebox.showerror("Connexion refusée", "Mot de passe administrateur incorrect.")
        else:
            expected = auth.get_effective_user_password(cfg)
            if pwd == expected:
                self.app.role = "user"
                self.app.show_main()
            else:
                messagebox.showerror("Connexion refusée",
                                      "Mot de passe utilisateur incorrect ou expiré "
                                      "(il change chaque début de mois).")


# ==========================================================================
# ÉCRAN PRINCIPAL
# ==========================================================================

class MainScreen(ttk.Frame):
    def __init__(self, parent, app: App):
        super().__init__(parent)
        self.app = app
        self.pack(fill="both", expand=True)

        top = ttk.Frame(self)
        top.pack(fill="x")
        role_label = "Administrateur" if app.role == "admin" else "Utilisateur"
        ttk.Label(top, text=f"{APP_TITLE}  —  connecté en tant que {role_label}",
                  font=("Segoe UI", 11, "bold")).pack(side="left", padx=10, pady=8)
        ttk.Button(top, text="Se déconnecter", command=app.show_login).pack(side="right", padx=10, pady=8)

        banner = tk.Label(self, text=PAID_SOFTWARE_NOTICE, fg="white", bg="#b8860b",
                           font=("Segoe UI", 9, "bold"), pady=4)
        banner.pack(fill="x")

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)

        self.employees_tab = EmployeesTab(notebook, app)
        notebook.add(self.employees_tab, text="Saisie des employés")

        self.payroll_tab = PayrollTab(notebook, app, self.employees_tab)
        notebook.add(self.payroll_tab, text="Bulletins / État de paie")

        if app.role == "admin":
            self.params_tab = ParamsTab(notebook, app)
            notebook.add(self.params_tab, text="Paramètres de paie")

            self.security_tab = SecurityTab(notebook, app)
            notebook.add(self.security_tab, text="Sécurité / Mots de passe")


# ==========================================================================
# ONGLET SAISIE DES EMPLOYÉS
# ==========================================================================

COLUMNS = [
    ("numero", "N°", 40),
    ("nom_prenoms", "Nom & Prénoms", 160),
    ("classification", "Classif.", 70),
    ("salaire_base", "Sal. Base", 85),
    ("prime_anciennete", "Prime anc.", 80),
    ("heures_sup", "Heures Sup", 80),
    ("sursalaire", "Sursalaire", 80),
    ("gratification", "Gratif.", 80),
    ("indemnite_caisse", "Indem. Caisse", 90),
    ("indemnite_logement", "Indem. Log.", 90),
    ("indemnite_fonction", "Indem. Fct.", 90),
    ("indemnite_transport", "Indem. Trprt", 90),
    ("personnes_a_charge", "Pers. charge", 85),
    ("retenue_pret", "Retenue prêt", 90),
]


class EmployeesTab(ttk.Frame):
    def __init__(self, parent, app: App):
        super().__init__(parent)
        self.app = app

        left = ttk.Frame(self)
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))

        cols = [c[0] for c in COLUMNS]
        self.tree = ttk.Treeview(left, columns=cols, show="headings", height=20)
        for key, label, width in COLUMNS:
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, anchor="center")
        self.tree.pack(fill="both", expand=True, side="left")

        vsb = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")

        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        right = ttk.Frame(self, width=320)
        right.pack(side="right", fill="y")

        ttk.Label(right, text="Fiche employé", font=("Segoe UI", 11, "bold")).pack(pady=(4, 10))

        self.form_vars = {}
        form = ttk.Frame(right)
        form.pack(fill="x", padx=8)

        fields = [
            ("nom_prenoms", "Nom & Prénoms", "text"),
            ("classification", "Classification", "combo"),
            ("salaire_base", "Salaire de base", "num"),
            ("prime_anciennete", "Prime d'ancienneté", "num"),
            ("heures_sup", "Heures supplémentaires", "num"),
            ("sursalaire", "Sursalaire", "num"),
            ("gratification", "Gratification", "num"),
            ("indemnite_caisse", "Indemnité Caisse", "num"),
            ("indemnite_logement", "Indemnité Logement", "num"),
            ("indemnite_fonction", "Indemnité Fonction", "num"),
            ("indemnite_transport", "Indemnité Transport", "num"),
            ("personnes_a_charge", "Personnes à charge", "num"),
            ("retenue_pret", "Retenue prêt/avance", "num"),
        ]
        for i, (key, label, kind) in enumerate(fields):
            ttk.Label(form, text=label).grid(row=i, column=0, sticky="w", pady=2)
            var = tk.StringVar()
            if kind == "combo":
                w = ttk.Combobox(form, textvariable=var, values=["CADRE", "AUTRE"],
                                  state="readonly", width=18)
                var.set("AUTRE")
            else:
                w = ttk.Entry(form, textvariable=var, width=20)
                if kind == "num":
                    var.set("0")
            w.grid(row=i, column=1, pady=2, sticky="w")
            self.form_vars[key] = var

        btns = ttk.Frame(right)
        btns.pack(pady=14)
        ttk.Button(btns, text="Ajouter", command=self.add_employee).grid(row=0, column=0, padx=4)
        ttk.Button(btns, text="Mettre à jour", command=self.update_employee).grid(row=0, column=1, padx=4)
        ttk.Button(btns, text="Supprimer", command=self.delete_employee).grid(row=0, column=2, padx=4)
        ttk.Button(right, text="Vider le formulaire", command=self.clear_form).pack()

        self.selected_numero = None
        self.refresh_tree()

    # ------------------------------------------------------------------
    def get_employees(self):
        return self.app.config_data["employees"]

    def refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        for emp in self.get_employees():
            values = [emp.get(k, "") for k, _, _ in COLUMNS]
            self.tree.insert("", "end", iid=str(emp["numero"]), values=values)

    def _read_form(self):
        v = self.form_vars
        try:
            emp = Employee(
                numero=self.selected_numero or self.app.config_data["next_numero"],
                nom_prenoms=v["nom_prenoms"].get().strip(),
                classification=v["classification"].get() or "AUTRE",
                salaire_base=float(v["salaire_base"].get() or 0),
                prime_anciennete=float(v["prime_anciennete"].get() or 0),
                heures_sup=float(v["heures_sup"].get() or 0),
                sursalaire=float(v["sursalaire"].get() or 0),
                gratification=float(v["gratification"].get() or 0),
                indemnite_caisse=float(v["indemnite_caisse"].get() or 0),
                indemnite_logement=float(v["indemnite_logement"].get() or 0),
                indemnite_fonction=float(v["indemnite_fonction"].get() or 0),
                indemnite_transport=float(v["indemnite_transport"].get() or 0),
                personnes_a_charge=int(float(v["personnes_a_charge"].get() or 0)),
                retenue_pret=float(v["retenue_pret"].get() or 0),
                date_saisie=datetime.date.today().isoformat(),
            )
        except ValueError:
            messagebox.showerror("Erreur de saisie", "Merci de vérifier les valeurs numériques saisies.")
            return None
        if not emp.nom_prenoms:
            messagebox.showerror("Erreur de saisie", "Le nom de l'employé est obligatoire.")
            return None
        return emp

    def add_employee(self):
        emp = self._read_form()
        if emp is None:
            return
        emp.numero = self.app.config_data["next_numero"]
        self.app.config_data["employees"].append(emp.to_dict())
        self.app.config_data["next_numero"] += 1
        storage.save(self.app.config_data)
        self.refresh_tree()
        self.clear_form()

    def update_employee(self):
        if self.selected_numero is None:
            messagebox.showinfo("Info", "Sélectionnez d'abord un employé dans la liste.")
            return
        emp = self._read_form()
        if emp is None:
            return
        employees = self.app.config_data["employees"]
        for i, e in enumerate(employees):
            if e["numero"] == self.selected_numero:
                employees[i] = emp.to_dict()
                break
        storage.save(self.app.config_data)
        self.refresh_tree()

    def delete_employee(self):
        if self.selected_numero is None:
            messagebox.showinfo("Info", "Sélectionnez d'abord un employé dans la liste.")
            return
        if not messagebox.askyesno("Confirmer", "Supprimer cet employé ?"):
            return
        employees = self.app.config_data["employees"]
        self.app.config_data["employees"] = [e for e in employees if e["numero"] != self.selected_numero]
        storage.save(self.app.config_data)
        self.refresh_tree()
        self.clear_form()

    def clear_form(self):
        self.selected_numero = None
        for key, var in self.form_vars.items():
            var.set("AUTRE" if key == "classification" else ("0" if key != "nom_prenoms" else ""))
        self.tree.selection_remove(self.tree.selection())

    def on_select(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        numero = int(sel[0])
        self.selected_numero = numero
        emp = next((e for e in self.get_employees() if e["numero"] == numero), None)
        if not emp:
            return
        for key, var in self.form_vars.items():
            var.set(str(emp.get(key, "")))


# ==========================================================================
# ONGLET BULLETINS / ÉTAT DE PAIE
# ==========================================================================

class PayrollTab(ttk.Frame):
    def __init__(self, parent, app: App, employees_tab: EmployeesTab):
        super().__init__(parent)
        self.app = app
        self.employees_tab = employees_tab

        top = ttk.Frame(self)
        top.pack(fill="x", pady=6, padx=6)

        today = datetime.date.today()
        ttk.Label(top, text="Période de paie :").pack(side="left")
        self.mois_var = tk.StringVar(value=MOIS_FR[today.month - 1])
        ttk.Combobox(top, textvariable=self.mois_var, values=MOIS_FR, state="readonly",
                     width=12).pack(side="left", padx=6)
        self.annee_var = tk.StringVar(value=str(today.year))
        ttk.Entry(top, textvariable=self.annee_var, width=6).pack(side="left")

        ttk.Button(top, text="Calculer la paie", command=self.calculate).pack(side="left", padx=16)
        ttk.Button(top, text="Exporter vers Excel", command=self.export_excel).pack(side="left")

        result_cols = ["numero", "nom_prenoms", "remuneration_totale", "cnss_salariale",
                        "salaire_brut", "base_imposable", "iuts_net", "salaire_net",
                        "retenue_pret", "net_percu", "cout_total_employeur"]
        headers = ["N°", "Nom & Prénoms", "Rém. Totale", "CNSS", "Sal. Brut",
                   "Base Imposable", "IUTS", "Salaire Net", "Ret. Prêt",
                   "Net Perçu", "Coût Employeur"]

        self.result_cols = result_cols
        self.tree = ttk.Treeview(self, columns=result_cols, show="headings", height=20)
        for key, label in zip(result_cols, headers):
            self.tree.heading(key, text=label)
            self.tree.column(key, width=105, anchor="center")
        self.tree.pack(fill="both", expand=True, padx=6, pady=6)

        totals = ttk.Frame(self)
        totals.pack(fill="x", padx=6, pady=(0, 6))
        self.totals_label = ttk.Label(totals, text="", font=("Segoe UI", 10, "bold"))
        self.totals_label.pack(side="left")

        self.last_results = []

    def calculate(self):
        params = self.app.config_data["params"]
        employees = self.app.config_data["employees"]
        self.tree.delete(*self.tree.get_children())
        results = []
        total_net = total_cnss = total_iuts = total_cout = 0.0
        for e in employees:
            emp = Employee(**e)
            r = compute_payslip(emp, params)
            results.append(r)
            values = [r[k] for k in self.result_cols]
            self.tree.insert("", "end", values=values)
            total_net += r["net_percu"]
            total_cnss += r["cnss_total"]
            total_iuts += r["iuts_net"]
            total_cout += r["cout_total_employeur"]
        self.last_results = results
        self.totals_label.config(
            text=(f"Total Net Perçu : {total_net:,.0f}  |  Total CNSS : {total_cnss:,.0f}  |  "
                  f"Total IUTS : {total_iuts:,.0f}  |  Coût total employeur : {total_cout:,.0f}  FCFA")
            .replace(",", " ")
        )
        if not employees:
            messagebox.showinfo("Info", "Aucun employé saisi pour le moment.")

    def export_excel(self):
        if not self.last_results:
            self.calculate()
        if not self.last_results:
            return
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment
        except ImportError:
            messagebox.showerror("Module manquant",
                                  "Le module 'openpyxl' n'est pas installé.\n"
                                  "Installez-le avec : pip install openpyxl")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Classeur Excel", "*.xlsx")],
            initialfile=f"Etat_de_paie_{self.mois_var.get()}_{self.annee_var.get()}.xlsx",
        )
        if not path:
            return

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "État de paie"

        title = f"ÉTAT DE PAIE — {self.mois_var.get().upper()} {self.annee_var.get()}"
        ws.merge_cells("A1:K1")
        ws["A1"] = title
        ws["A1"].font = Font(size=14, bold=True)

        headers = ["N°", "Nom & Prénoms", "Classification", "Rém. Totale", "CNSS Salariale",
                   "Salaire Brut", "Base Imposable", "IUTS Net", "Salaire Net",
                   "Retenue Prêt", "Net Perçu", "Coût Total Employeur"]
        ws.append([])
        ws.append(headers)
        header_row = ws.max_row
        for cell in ws[header_row]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="1F4E78")
            cell.alignment = Alignment(horizontal="center")

        for r in self.last_results:
            ws.append([
                r["numero"], r["nom_prenoms"], r["classification"], r["remuneration_totale"],
                r["cnss_salariale"], r["salaire_brut"], r["base_imposable"], r["iuts_net"],
                r["salaire_net"], r["retenue_pret"], r["net_percu"], r["cout_total_employeur"],
            ])

        for col in ws.columns:
            length = max((len(str(c.value)) for c in col if c.value is not None), default=10)
            ws.column_dimensions[col[0].column_letter].width = max(12, length + 2)

        notice_row = ws.max_row + 2
        ws.cell(row=notice_row, column=1, value=PAID_SOFTWARE_NOTICE).font = Font(italic=True, color="B8860B")

        wb.save(path)
        messagebox.showinfo("Export réussi", f"Fichier exporté :\n{path}")


# ==========================================================================
# ONGLET PARAMÈTRES (Administrateur uniquement)
# ==========================================================================

class ParamsTab(ttk.Frame):
    def __init__(self, parent, app: App):
        super().__init__(parent)
        self.app = app
        params = app.config_data["params"]

        canvas = tk.Canvas(self, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.vars = {}
        row = 0

        def section(title):
            nonlocal row
            ttk.Label(inner, text=title, font=("Segoe UI", 11, "bold")).grid(
                row=row, column=0, columnspan=2, sticky="w", pady=(14, 4), padx=8)
            row += 1

        def field(label, key, value):
            nonlocal row
            ttk.Label(inner, text=label).grid(row=row, column=0, sticky="w", padx=8, pady=2)
            var = tk.StringVar(value=str(value))
            ttk.Entry(inner, textvariable=var, width=16).grid(row=row, column=1, sticky="w", padx=8, pady=2)
            self.vars[key] = var
            row += 1

        section("1. Cotisations CNSS")
        field("Taux CNSS salarié", "taux_cnss_salarie", params["taux_cnss_salarie"])
        field("Plafond mensuel soumis à CNSS", "plafond_cnss", params["plafond_cnss"])
        field("Cotisation CNSS salariale plafonnée", "cnss_salariale_plafonnee", params["cnss_salariale_plafonnee"])
        field("Taux CNSS patronale", "taux_cnss_patronale", params["taux_cnss_patronale"])
        field("Taux TPA", "taux_tpa", params["taux_tpa"])
        field("Retenue obligatoire sur salaire net", "taux_retenue_obligatoire", params["taux_retenue_obligatoire"])

        section("2. Abattement forfaitaire (IUTS)")
        field("Taux abattement CADRE", "abattement_cadre", params["abattement_cadre"])
        field("Taux abattement AUTRE", "abattement_autre", params["abattement_autre"])

        section("3. Plafond fiscal")
        field("Taux du plafond fiscal", "taux_plafond_fiscal", params["taux_plafond_fiscal"])

        section("4. Exonération des indemnités (taux, plafond)")
        field("Logement — taux exonéré", "exo_logement_taux", params["exo_logement"][0])
        field("Logement — plafond mensuel", "exo_logement_plafond", params["exo_logement"][1])
        field("Fonction — taux exonéré", "exo_fonction_taux", params["exo_fonction"][0])
        field("Fonction — plafond mensuel", "exo_fonction_plafond", params["exo_fonction"][1])
        field("Transport — taux exonéré", "exo_transport_taux", params["exo_transport"][0])
        field("Transport — plafond mensuel", "exo_transport_plafond", params["exo_transport"][1])

        section("Barème IUTS et réduction pour charges de famille")
        ttk.Label(inner, text="(modifiables uniquement dans le fichier de données JSON — "
                               "voir le bouton ci-dessous)", foreground="#666").grid(
            row=row, column=0, columnspan=2, sticky="w", padx=8)
        row += 1

        ttk.Button(inner, text="Ouvrir le dossier des données",
                   command=self.open_data_folder).grid(row=row, column=0, pady=16, padx=8, sticky="w")
        ttk.Button(inner, text="Enregistrer les paramètres",
                   command=self.save_params).grid(row=row, column=1, pady=16, padx=8, sticky="w")

    def save_params(self):
        try:
            p = self.app.config_data["params"]
            v = self.vars
            p["taux_cnss_salarie"] = float(v["taux_cnss_salarie"].get())
            p["plafond_cnss"] = float(v["plafond_cnss"].get())
            p["cnss_salariale_plafonnee"] = float(v["cnss_salariale_plafonnee"].get())
            p["taux_cnss_patronale"] = float(v["taux_cnss_patronale"].get())
            p["taux_tpa"] = float(v["taux_tpa"].get())
            p["taux_retenue_obligatoire"] = float(v["taux_retenue_obligatoire"].get())
            p["abattement_cadre"] = float(v["abattement_cadre"].get())
            p["abattement_autre"] = float(v["abattement_autre"].get())
            p["taux_plafond_fiscal"] = float(v["taux_plafond_fiscal"].get())
            p["exo_logement"] = [float(v["exo_logement_taux"].get()), float(v["exo_logement_plafond"].get())]
            p["exo_fonction"] = [float(v["exo_fonction_taux"].get()), float(v["exo_fonction_plafond"].get())]
            p["exo_transport"] = [float(v["exo_transport_taux"].get()), float(v["exo_transport_plafond"].get())]
        except ValueError:
            messagebox.showerror("Erreur", "Merci de vérifier les valeurs saisies (nombres attendus).")
            return
        storage.save(self.app.config_data)
        messagebox.showinfo("Enregistré", "Paramètres de paie mis à jour.")

    def open_data_folder(self):
        import subprocess, sys, os as _os
        path = storage.get_data_dir()
        try:
            if sys.platform.startswith("win"):
                _os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception:
            messagebox.showinfo("Dossier de données", path)


# ==========================================================================
# ONGLET SÉCURITÉ (Administrateur uniquement)
# ==========================================================================

class SecurityTab(ttk.Frame):
    def __init__(self, parent, app: App):
        super().__init__(parent)
        self.app = app

        frame = ttk.Frame(self)
        frame.pack(padx=20, pady=20, anchor="nw")

        ttk.Label(frame, text="Mot de passe Utilisateur du mois en cours",
                  font=("Segoe UI", 12, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        period = auth.current_period()
        current_pwd = auth.get_effective_user_password(app.config_data)
        ttk.Label(frame, text=f"Période : {period}").grid(row=1, column=0, sticky="w")
        self.pwd_display = tk.StringVar(value=current_pwd)
        entry = ttk.Entry(frame, textvariable=self.pwd_display, width=20, state="readonly",
                           font=("Consolas", 12, "bold"))
        entry.grid(row=2, column=0, sticky="w", pady=6)
        ttk.Label(frame, text="(généré automatiquement — change chaque 1er du mois)",
                  foreground="#666").grid(row=3, column=0, sticky="w")

        ttk.Separator(frame).grid(row=4, column=0, columnspan=2, sticky="ew", pady=16)

        ttk.Label(frame, text="Forcer un mot de passe Utilisateur pour ce mois-ci",
                  font=("Segoe UI", 11, "bold")).grid(row=5, column=0, columnspan=2, sticky="w")
        self.override_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.override_var, width=20).grid(row=6, column=0, sticky="w", pady=6)
        ttk.Button(frame, text="Appliquer", command=self.apply_override).grid(row=6, column=1, padx=8)
        ttk.Button(frame, text="Revenir à la génération automatique",
                   command=self.clear_override).grid(row=7, column=0, columnspan=2, sticky="w", pady=(0, 6))

        ttk.Separator(frame).grid(row=8, column=0, columnspan=2, sticky="ew", pady=16)

        ttk.Label(frame, text="Changer le mot de passe Administrateur",
                  font=("Segoe UI", 11, "bold")).grid(row=9, column=0, columnspan=2, sticky="w")
        self.new_admin_pwd = tk.StringVar()
        ttk.Entry(frame, textvariable=self.new_admin_pwd, width=20, show="•").grid(
            row=10, column=0, sticky="w", pady=6)
        ttk.Button(frame, text="Changer", command=self.change_admin_password).grid(row=10, column=1, padx=8)

        ttk.Separator(frame).grid(row=11, column=0, columnspan=2, sticky="ew", pady=16)
        ttk.Label(frame, text=PAID_SOFTWARE_NOTICE, foreground="#b8860b",
                  font=("Segoe UI", 9, "italic")).grid(row=12, column=0, columnspan=2, sticky="w")

    def apply_override(self):
        pwd = self.override_var.get().strip()
        if not pwd:
            messagebox.showerror("Erreur", "Saisissez un mot de passe.")
            return
        period = auth.current_period()
        self.app.config_data.setdefault("user_password_overrides", {})[period] = pwd
        storage.save(self.app.config_data)
        self.pwd_display.set(pwd)
        messagebox.showinfo("Appliqué", f"Mot de passe Utilisateur forcé pour {period}.")

    def clear_override(self):
        period = auth.current_period()
        self.app.config_data.get("user_password_overrides", {}).pop(period, None)
        storage.save(self.app.config_data)
        auto_pwd = auth.get_effective_user_password(self.app.config_data)
        self.pwd_display.set(auto_pwd)
        messagebox.showinfo("Réinitialisé", "Le mot de passe Utilisateur est de nouveau généré automatiquement.")

    def change_admin_password(self):
        pwd = self.new_admin_pwd.get().strip()
        if len(pwd) < 6:
            messagebox.showerror("Erreur", "Le mot de passe doit contenir au moins 6 caractères.")
            return
        salt, digest = auth.hash_password(pwd)
        self.app.config_data["admin_salt"] = salt
        self.app.config_data["admin_hash"] = digest
        storage.save(self.app.config_data)
        self.new_admin_pwd.set("")
        messagebox.showinfo("Changé", "Mot de passe administrateur mis à jour.")


# ==========================================================================

if __name__ == "__main__":
    app = App()
    app.mainloop()
