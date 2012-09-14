import numpy
from ufl import *
from pyop2 import ffc_interface, op2

import state_types as fluidity_state
from state_types import *
from ufl_expr import *

valuetype = numpy.float64
op2.init()

class FieldDict(dict):

    def __getitem__(self, key):
        return super(FieldDict, self).__getitem__(key)

# from http://www.toofishes.net/blog/python-cached-property-decorator/
class cached_property(object):
    '''A read-only @property that is only evaluated once. The value is cached
    on the object itself rather than the function or class; this should prevent
    memory leakage.'''
    def __init__(self, fget, doc=None):
        self.fget = fget
        self.__doc__ = doc or fget.__doc__
        self.__name__ = fget.__name__
        self.__module__ = fget.__module__

    def __get__(self, obj, cls):
        if obj is None:
            return self
        obj.__dict__[self.__name__] = result = self.fget(obj)
        return result

field2rank = {'ScalarField': 0,
              'VectorField': 1,
              'TensorField': 2}

field2element = {'ScalarField': FiniteElement,
                 'VectorField': VectorElement,
                 'TensorField': TensorElement}

dimloc2cell = {1: {1: 'vertex', 2: 'interval'},
               2: {3: 'triangle', 4: 'quadrilateral'},
               3: {4: 'tetrahedron', 6: 'hexahedron'}}

type2family = {'lagrangian': 'Lagrange'}

def ufl_cell(element):
    try:
        return dimloc2cell[element.dimension][element.quadrature.loc]
    except KeyError:
        raise RuntimeError("Elements of dimension %d and loc %d are not suppported" \
                % (element.dimension, element.loc))

def ufl_family(field):
    try:
        return "%s%s" % ("Discontinuous " if field.mesh.continuity < 0 else "", \
                         type2family[field.fluidity_element.type])
    except KeyError:
        raise RuntimeError("Elements of type %s are not supported" % field.fluidity_element.type)

def ufl_element(field):
    e = field.fluidity_element
    return field2element[field.description](ufl_family(field), ufl_cell(e), e.degree)

class Mesh(fluidity_state.Mesh):

    @cached_property
    def element_set(self):
        return op2.Set(self.element_count, "%s_elements" % self.name)

    @cached_property
    def node_set(self):
        return op2.Set(self.node_count, "%s_nodes" % self.name)

    @cached_property
    def element_node_map(self):
        return op2.Map(self.element_set, self.node_set, self.shape.loc, \
                self.ndglno - 1, "%s_elem_node" % self.name)

class FieldCoefficient(Coefficient):
    """Coefficient derived from a Fluidity field."""

    @property
    def value_shape(self):
        return (self.mesh.shape.dimension,)*self.rank() or 1

    @property
    def element_set(self):
        return self.mesh.element_set

    @cached_property
    def node_set(self):
        return op2.Set(self.node_count, "%s_nodes" % self.name)

    @cached_property
    def dat(self):
        return op2.Dat(self.node_set, self.value_shape, \
                self.val, valuetype, self.name)

    @cached_property
    def element_node_map(self):
        return op2.Map(self.mesh.element_set, self.node_set, self.mesh.shape.loc, \
                self.mesh.ndglno - 1, "%s_elem_node" % self.name)

    def temporary_dat(self, name):
        return op2.Dat(self.node_set, self.value_shape, \
                numpy.zeros(self.node_count), valuetype, name)

class ScalarField(FieldCoefficient, fluidity_state.ScalarField):

    def __init__(self,n,v,ft,op,uid,mesh=None,element=None,count=None):
        fluidity_state.ScalarField.__init__(self, n, v, ft, op, uid, mesh)
        FieldCoefficient.__init__(self, element or ufl_element(self), count)

    @property
    def fluidity_element(self):
        return fluidity_state.ScalarField.shape(self)

    def _reconstruct(self, element, count):
        # This code is class specific
        return ScalarField(self.name, self.val, self.field_type, self.option_path,
                self.uid, self.mesh, element, count)

class VectorField(FieldCoefficient, fluidity_state.VectorField):

    def __init__(self,n,v,ft,op,dim,uid,mesh=None,element=None,count=None):
        fluidity_state.VectorField.__init__(self, n, v, ft, op, dim, uid, mesh)
        FieldCoefficient.__init__(self, element or ufl_element(self), count)

    @property
    def fluidity_element(self):
        return fluidity_state.VectorField.shape(self)

    def _reconstruct(self, element, count):
        # This code is class specific
        return VectorField(self.name, self.val, self.field_type, self.option_path,
                self.dimension, self.uid, self.mesh, element, count)

class TensorField(FieldCoefficient, fluidity_state.TensorField):

    def __init__(self,n,v,ft,op,dim0,dim1,uid,mesh=None,element=None,count=None):
        fluidity_state.TensorField.__init__(self, n, v, ft, op, dim0, dim1, uid, mesh)
        FieldCoefficient.__init__(self, element or ufl_element(self), count)

    @property
    def fluidity_element(self):
        return fluidity_state.TensorField.shape(self)

    def _reconstruct(self, element, count):
        # This code is class specific
        return TensorField(self.name, self.val, self.field_type, self.option_path,
                self.dimension[0], self.dimension[1], self.uid,
                self.mesh, element, count)

from solving import solve
