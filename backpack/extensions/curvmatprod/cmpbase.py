from backpack.utils.unsqueeze import hmp_unsqueeze_if_missing_dim
from backpack.extensions.curvature import Curvature
from backpack.extensions.module_extension import ModuleExtension
from backpack.utils.einsum import einsum


class CMPBase(ModuleExtension):
    """
    Given matrix-vector product routine `MVP(A)` backpropagate to `MVP(J^T A J)`.
    """

    def __init__(self, derivatives, params=None):
        super().__init__(params=params)
        self.derivatives = derivatives

    def backpropagate(self, ext, module, g_inp, g_out, backproped):
        """Backpropagate Hessian multiplication routines.

        Given mat → ℋz(x) mat, backpropagate mat → ℋx mat.
        """
        GGN_mat_prod = self._make_GGN_mat_prod(ext, module, g_inp, g_out, backproped)

        R_required = self._require_residual(ext, module, g_inp, g_out, backproped)
        if R_required:
            R_mat_prod = self._make_R_mat_prod(ext, module, g_inp, g_out, backproped)

        @hmp_unsqueeze_if_missing_dim(mat_dim=3)
        def CMP_in(mat):
            """Multiplication with curvature matrix w.r.t. the module input.

            Parameters:
            -----------
            mat : torch.Tensor
                Matrix that will be multiplied.
            """
            out = GGN_mat_prod(mat)

            if R_required:
                out.add_(R_mat_prod(mat))

            return out

        return CMP_in

    def _make_GGN_mat_prod(self, ext, module, g_inp, g_out, backproped):
        """Return multiplication routine with the first HBP term."""
        CMP_out = backproped

        def GGN_mat_prod(mat):
            """Multiply with the GGN term: mat → [𝒟z(x)ᵀ ℋz 𝒟z(x)] mat.

            First term of the module input Hessian backpropagation equation.
            """
            Jmat = self.derivatives.jac_mat_prod(module, g_inp, g_out, mat)
            CJmat = CMP_out(Jmat)
            JTCJmat = self.derivatives.jac_t_mat_prod(module, g_inp, g_out, CJmat)

            return JTCJmat

        return GGN_mat_prod

    def _require_residual(self, ext, module, g_inp, g_out, backproped):
        """Is the residual term required for multiply with the curvature?"""
        vanishes = self.derivatives.hessian_is_zero()
        neglected = not Curvature.require_residual(ext.get_curv_type())

        return not (vanishes or neglected)

    def _make_R_mat_prod(self, ext, module, g_inp, g_out, backproped):
        """Return multiplication routine with the second HBP term."""

        if not self.derivatives.hessian_is_diagonal():
            # TODO: Allow for non-diagonal residuals (e.g. BatchNorm)
            # No PCH (no cheap way to cast the residual PSD)
            raise NotImplementedError(
                "Residual terms are only supported for elementwise functions"
            )

        else:
            R_mat_prod = self.__make_diagonal_R_mat_prod(
                ext, module, g_inp, g_out, backproped
            )

        return R_mat_prod

    def __make_diagonal_R_mat_prod(self, ext, module, g_inp, g_out, backproped):
        # TODO Refactor core: hessian_diagonal -> residual_diagonal
        R = self.derivatives.hessian_diagonal(module, g_inp, g_out)
        R_mod = Curvature.modify_residual(R, ext.get_curv_type())

        def R_mat_prod(mat):
            """Multiply with the residual: mat → [∑_{k} Hz_k(x) 𝛿z_k] mat.

            Second term of the module input Hessian backpropagation equation.
            """
            return einsum("bi,bic->bic", (R_mod, mat))

        return R_mat_prod
