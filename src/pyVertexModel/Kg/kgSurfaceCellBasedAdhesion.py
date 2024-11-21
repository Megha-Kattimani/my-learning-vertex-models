import time

import numpy as np

from src.pyVertexModel.Kg import kg_functions
from src.pyVertexModel.Kg.kg import Kg, add_noise_to_parameter


class KgSurfaceCellBasedAdhesion(Kg):
    """
    Class to compute the work and Jacobian for the SurfaceCellBasedAdhesion energy.
    """
    def compute_work(self, Geo, Set, Geo_n=None, calculate_K=True):
        Energy = {}
        start = time.time()

        for c in [cell.ID for cell in Geo.Cells if cell.AliveStatus == 1]:

            if Geo.remodelling and not np.isin(c, Geo.AssembleNodes):
                continue

            Cell = Geo.Cells[c]
            Energy_c = self.work_per_cell(Cell, Geo, Set, calculate_K)
            Energy[c] = Energy_c

        self.energy = sum(Energy.values())

        end = time.time()
        self.timeInSeconds = f"Time at SurfaceCell: {end - start} seconds"

    def work_per_cell(self, Cell, Geo, Set, calculate_K=True):
        Energy_c = 0
        Ys = Cell.Y
        ge = np.zeros(self.g.shape, dtype=self.precision_type)
        fact0 = 0

        Cell.lambda_s1_noise = add_noise_to_parameter(Set.lambdaS1, 0)
        Cell.lambda_s2_noise = add_noise_to_parameter(Set.lambdaS2, 0)
        Cell.lambda_s3_noise = add_noise_to_parameter(Set.lambdaS3, 0)

        # Calculate the fact0 for each type of interface
        for face in Cell.Faces:
            if face.InterfaceType == 'Top' or face.InterfaceType == 0:
                Lambda = Cell.lambda_s1_noise
            elif face.InterfaceType == 'CellCell' or face.InterfaceType == 1:
                Lambda = Cell.lambda_s2_noise
            elif face.InterfaceType == 'Bottom' or face.InterfaceType == 2:
                Lambda = Cell.lambda_s3_noise
            else:
                raise ValueError(f"InterfaceType {face.InterfaceType} not recognized")

            fact0 += (Lambda * (face.Area - face.Area0))

        fact = fact0 / Cell.Area0 ** 2

        for face in Cell.Faces:
            if face.InterfaceType == 'Top' or face.InterfaceType == 0:
                Lambda = Cell.lambda_s1_noise
            elif face.InterfaceType == 'CellCell' or face.InterfaceType == 1:
                Lambda = Cell.lambda_s2_noise
            elif face.InterfaceType == 'Bottom' or face.InterfaceType == 2:
                Lambda = Cell.lambda_s3_noise
            else:
                raise ValueError(f"InterfaceType {face.InterfaceType} not recognized")

            for t in face.Tris:
                if not np.all(np.isin(Cell.globalIds[t.Edge], Geo.y_ablated)):
                    y1 = Ys[t.Edge[0]]
                    y2 = Ys[t.Edge[1]]
                    y3 = face.Centre
                    n3 = face.globalIds
                    nY = [Cell.globalIds[edge] for edge in t.Edge] + [n3]

                    if Geo.remodelling and not np.any(np.isin(nY, Cell.vertices_and_faces_to_remodel)):
                        continue

                    if calculate_K:
                        ge = self.calculate_kg(Lambda, fact, ge, nY, y1, y2, y3)
                    else:
                        ge = self.calculate_g(Lambda, ge, nY, y1, y2, y3)

        self.g += ge * fact
        if calculate_K:
            self.K = kg_functions.compute_finalK_SurfaceEnergy(ge, self.K, Cell.Area0)

        Energy_c += (1 / 2) * fact0 * fact

        Cell.lambda_s1_noise = None
        Cell.lambda_s2_noise = None
        Cell.lambda_s3_noise = None

        return Energy_c

    def calculate_kg(self, Lambda, fact, ge, nY, y1, y2, y3):
        gs, Ks, Kss = kg_functions.gKSArea(y1, y2, y3)
        gs = Lambda * gs
        ge = self.assemble_g(ge, gs, np.array(nY, dtype='int'))
        Ks = np.dot(fact * Lambda, (Ks + Kss))

        self.assemble_k(Ks, np.array(nY, dtype='int'))
        return ge

    def calculate_g(self, Lambda, ge, nY, y1, y2, y3):
        gs, _, _ = self.gKSArea(y1, y2, y3)
        gs = Lambda * gs
        ge = self.assemble_g(ge, gs, np.array(nY, dtype='int'))
        return ge

    def compute_final_k_surface_energy(self, ge, K, Area0):
        """
        Helper function to compute the final K for the Surface energy.
        :param ge: The residual g.
        :param K: The Jacobian K.
        :param Area0: The initial area of the cell.
        :return: The final K.
        """
        ge_ = ge.reshape((ge.size, 1))
        ge_transpose = ge.reshape((1, ge.size))

        return K + np.dot(ge_, ge_transpose) / Area0 ** 2
