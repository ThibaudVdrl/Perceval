# MIT License
#
# Copyright (c) 2022 Quandela
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from .source import Source
from .circuit import ACircuit, Circuit
from perceval.utils import SVDistribution, BasicState, StateVector, global_params
from perceval.backends import Backend
from typing import Dict, Callable, Type, Literal


class Processor:
    """
        Generic definition of processor as sources + circuit
    """
    def __init__(self, sources: Dict[int, Source], circuit: ACircuit, post_select_fn: Callable = None,
                 heralds: Dict[int, int] = {}):
        r"""Define a processor with sources connected to the circuit and possible post_selection

        :param sources: a list of Source used by the processor
        :param circuit: a circuit define the processor internal logic
        :param post_select_fn: a post-selection function
        """
        self._sources = sources
        self._circuit = circuit
        self._post_select = post_select_fn
        self._heralds = heralds
        self._inputs_map = None
        for k in range(circuit.m):
            if k in sources:
                distribution = sources[k].probability_distribution()
            else:
                distribution = SVDistribution(StateVector("|0>"))
            # combine distributions
            if self._inputs_map is None:
                self._inputs_map = distribution
            else:
                self._inputs_map *= distribution
        self._in_port_names = {}
        self._out_port_names = {}

    def set_port_names(self, in_port_names: Dict[int, str], out_port_names: Dict[int, str] = {}):
        self._in_port_names = in_port_names
        self._out_port_names = out_port_names

    @property
    def source_distribution(self):
        return self._inputs_map

    @property
    def circuit(self):
        return self._circuit

    @property
    def sources(self):
        return self._sources

    def filter_herald(self, s: BasicState, keep_herald: bool) -> StateVector:
        if not self._heralds or keep_herald:
            return StateVector(s)
        new_state = []
        for idx, k in enumerate(s):
            if idx not in self._heralds:
                new_state.append(k)
        return StateVector(new_state)

    def run(self, simulator_backend: Type[Backend], keep_herald: bool=False):
        """
            calculate the output probabilities - returns performance, and output_maps
        """
        # first generate all possible outputs
        sim = simulator_backend(self._circuit.compute_unitary(use_symbolic=False))
        # now generate all possible outputs
        outputs = SVDistribution()
        for input_state, input_prob in self._inputs_map.items():
            for (output_state, p) in sim.allstateprob_iterator(input_state):
                if p > global_params['min_p'] and self._state_selected(output_state):
                    outputs[self.filter_herald(output_state, keep_herald)] += p*input_prob
        all_p = sum(v for v in outputs.values())
        if all_p == 0:
            return 0, outputs
        # normalize probabilities
        for k in outputs.keys():
            outputs[k] /= all_p
        return all_p, outputs

    def _state_selected(self, state: BasicState) -> bool:
        """
        Computes if the state is selected given heralds and post selection function
        """
        for m, v in self._heralds.items():
            if state[m] != v:
                return False
        if self._post_select is not None:
            return self._post_select(state)
        return True
