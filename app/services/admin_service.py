"""Reglas de las estadisticas de la plataforma.

Mismo criterio que los reportes del usuario: el backend calcula y el frontend
solo pinta. Aqui ademas se decide cuales son los rangos —una semana, un mes—
para que la pantalla no tenga que saber que significa "reciente".
"""

from datetime import date, timedelta

from app.repositories.admin_repository import AdminRepository


class AdminService:
    """Como va Bolsillo, en numeros."""

    def __init__(self, repo: AdminRepository):
        self._repo = repo

    def estadisticas(self) -> dict:
        """Todo lo que muestra el panel de administracion, en una peticion.

        Va junto y no en cinco endpoints porque se muestra junto: son cinco
        consultas cortas contra tablas indexadas, y partirlo obligaria a la
        pantalla a encadenar peticiones para pintar una sola vista.
        """
        hoy = date.today()
        hace_7 = hoy - timedelta(days=7)
        hace_30 = hoy - timedelta(days=30)
        primero_del_mes = hoy.replace(day=1)

        total_usuarios, activos = self._repo.usuarios()
        entro, salio = self._repo.movido_en(primero_del_mes, hoy)

        return {
            "users": {
                "total": total_usuarios,
                "active": activos,
                #Los dados de baja: se resta aqui y no en la pantalla, que no
                #tiene por que saber que uno es el complemento del otro.
                "inactive": total_usuarios - activos,
                "new_last_7_days": self._repo.altas_desde(hace_7),
                "new_last_30_days": self._repo.altas_desde(hace_30),
                #Cuanta gente USA la aplicacion, que no es lo mismo que cuanta
                #se registro. La distancia entre las dos cifras es lo que dice
                #si el producto retiene o solo capta.
                "active_last_30_days": self._repo.usuarios_con_movimientos(hace_30),
            },
            "activity": {
                "transactions": self._repo.movimientos(),
                "transactions_last_30_days": self._repo.movimientos(hace_30),
                "accounts": self._repo.bolsillos(),
                "custom_categories": self._repo.categorias_propias(),
            },
            #Lo que movio la plataforma este mes. Sin transferencias: mover
            #plata entre bolsillos propios no es dinero que entre ni salga.
            "this_month": {
                "from": primero_del_mes,
                "to": hoy,
                "income": entro,
                "expense": salio,
            },
            "top_expense_categories": [
                {"name": nombre, "count": usos}
                for nombre, usos in self._repo.top_categorias()
            ],
        }
