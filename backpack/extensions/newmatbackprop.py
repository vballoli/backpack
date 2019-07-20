from backpack.extensions.module_extension import ModuleExtension


class MatToJacMat(ModuleExtension):

    def __init__(self, derivatives, params=None):
        super().__init__(params)
        self.derivatives = derivatives

    def backpropagate(self, ext, module, grad_inp, grad_out, backproped):

        if self.derivatives is None:
            return backproped

        if isinstance(backproped, list):
            M_list = [
                self.derivatives.jac_t_mat_prod(
                    module, inp, out, grad_inp, grad_out, M
                )
                for M in backproped
            ]
            return list(M_list)
        else:
            return self.derivatives.jac_t_mat_prod(
                module, inp, out, grad_inp, grad_out, backproped
            )
