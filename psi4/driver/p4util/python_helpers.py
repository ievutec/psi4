#
# @BEGIN LICENSE
#
# Psi4: an open-source quantum chemistry software package
#
# Copyright (c) 2007-2017 The Psi4 Developers.
#
# The copyrights for code used from other parties are included in
# the corresponding files.
#
# This file is part of Psi4.
#
# Psi4 is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, version 3.
#
# Psi4 is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with Psi4; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# @END LICENSE
#

import os
import re
import sys
import uuid
import numpy as np

from . import optproc
from psi4.driver import qcdb
from psi4 import core

## Python basis helps


@staticmethod
def pybuild_basis(mol, key=None, target=None, fitrole='ORBITAL', other=None, puream=-1, return_atomlist=False, quiet=False):
    if key == 'ORBITAL':
        key = 'BASIS'

    def _resolve_target(key, target):
        """Figure out exactly what basis set was intended by (key, target)
        """
        horde = qcdb.libmintsbasisset.basishorde
        if not target:
            if not key:
                key = 'BASIS'
            target = core.get_global_option(key)

        if target in horde:
            return horde[target]
        return target

    # Figure out what exactly was meant by 'target'.
    resolved_target = _resolve_target(key, target)

    # resolved_target needs to be either a string or function for pyconstuct.
    # if a string, they search for a gbs file with that name.
    # if a function, it needs to apply a basis to each atom.

    basisdict = qcdb.BasisSet.pyconstruct(mol.create_psi4_string_from_molecule(),
                                          key, resolved_target, fitrole, other, return_atomlist=return_atomlist)

    if return_atomlist:
        atom_basis_list = []
        for atbs in basisdict:
            atommol = core.Molecule.create_molecule_from_string(atbs['molecule'])
            lmbs = core.BasisSet.construct_from_pydict(atommol, atbs, puream)
            atom_basis_list.append(lmbs)
            #lmbs.print_detail_out()
        return atom_basis_list
    if ((sys.version_info < (3,0) and isinstance(resolved_target, basestring)) or
        (sys.version_info >= (3,0) and isinstance(resolved_target, str))):
        basisdict['name'] = basisdict['name'].split('/')[-1].replace('.gbs', '')
    if callable(resolved_target):
        basisdict['name'] = resolved_target.__name__.replace('basisspec_psi4_yo__', '').upper()

    if not quiet:
        core.print_out(basisdict['message'])

    if basisdict['key'] is None:
        basisdict['key'] = 'BASIS'
    psibasis = core.BasisSet.construct_from_pydict(mol, basisdict, puream)
    return psibasis

core.BasisSet.build = pybuild_basis

## Python wavefunction helps

@staticmethod
def pybuild_wavefunction(mol, basis=None):
    if basis is None:
        basis = core.BasisSet.build(mol)
    elif (sys.version_info[0] == 2) and isinstance(basis, (str, unicode)):
        basis = core.BasisSet.build(mol, "ORBITAL", basis)
    elif (sys.version_info[0] > 2) and isinstance(basis, str):
        basis = core.BasisSet.build(mol, "ORBITAL", basis)

    wfn = core.Wavefunction(mol, basis)
    return wfn

core.Wavefunction.build = pybuild_wavefunction

## Python JK helps

@staticmethod
def pybuild_JK(orbital_basis, aux=None, jk_type=None):
    """
    Constructs a Psi4 JK object from an input basis.

    Parameters
    ----------
    orbital_basis : :py:class:`~psi4.core.BasisSet`
        Orbital basis to use in the JK object.
    aux : :py:class:`~psi4.core.BasisSet`
        Optional auxiliary basis set for density-fitted tensors. Defaults
        to the DF_BASIS_SCF if set, otherwise the correspond JKFIT basis
        to the passed in orbital_basis.
    type : str
        Type of JK object to build (DF, Direct, PK, etc). Defaults to the
        current global SCF_TYPE option.

    Returns
    -------
    :py:class:`~psi4.core.JK`
        Uninitialized JK object.

    Example
    -------

    jk = psi4.core.JK.build(bas)
    jk.set_memory(int(5e8)) # 4GB of memory
    jk.initialize()

    ...

    jk.C_left_add(matirx)
    jk.compute()
    jk.C_clear()

    ...

    """

    optstash = optproc.OptionsState(["SCF_TYPE"])

    if jk_type is not None:
        core.set_global_option("SCF_TYPE", jk_type)

    if aux is None:
        if core.get_option("SCF", "SCF_TYPE") == "DF":
            aux = core.BasisSet.build(orbital_basis.molecule(), "DF_BASIS_SCF",
                                      core.get_option("SCF", "DF_BASIS_SCF"),
                                      "JKFIT", core.get_global_option('BASIS'),
                                      orbital_basis.has_puream())
        else:
            aux = core.BasisSet.zero_ao_basis_set()


    jk = core.JK.build_JK(orbital_basis, aux)

    optstash.restore()
    return jk

core.JK.build = pybuild_JK

## Grid Helpers

def get_np_xyzw(Vpot):
    """
    Returns the x, y, z, and weights of a grid as a tuple of NumPy array objects.
    """
    x_list = []
    y_list = []
    z_list = []
    w_list = []

    # Loop over every block in the potenital
    for b in range(Vpot.nblocks()):

        # Obtain the block
        block = Vpot.get_block(b)

        # Obtain the x, y, and z coordinates along with the weight
        x_list.append(block.x())
        y_list.append(block.y())
        z_list.append(block.z())
        w_list.append(block.w())

    x = np.hstack(x_list)
    y = np.hstack(y_list)
    z = np.hstack(z_list)
    w = np.hstack(w_list)

    return (x, y, z, w)

core.VBase.get_np_xyzw = get_np_xyzw

## Python other helps

core.Molecule.run_dftd3 = qcdb.interface_dftd3.run_dftd3
core.Molecule.run_gcp = qcdb.interface_gcp.run_gcp


def set_options(options_dict):
    """
    Sets Psi4 global options from an input dictionary.
    """

    for k, v, in options_dict.items():
        core.set_global_option(k.upper(), v)


def set_module_options(module, options_dict):
    """
    Sets Psi4 module options from a module specification and input dictionary.
    """

    for k, v, in options_dict.items():
        core.set_local_option(module.upper(), k.upper(), v)


## OEProp helpers


def pcm_helper(block):
    """
    Passes multiline string *block* to PCMSolver parser.

    Parameters
    ----------
    block: multiline string with PCM input in PCMSolver syntax.

    Notes
    -----
    !Warning! This function changes directory from launch site to scratch and
    back. This is needed because PCMSolver does not have a notion of an
    absolute paths for its input file. If you are looking at this function as
    an example, remember that changing directories is usually a **bad idea**
    and **should not be done**.
    """

    # Setup unique scratch directory and move in, as done for other add-ons
    psioh = core.IOManager.shared_object()
    psio = core.IO.shared_object()
    curdir = os.getcwd()
    os.chdir(psioh.get_default_path())
    pcm_tmpdir = 'psi.' + str(os.getpid()) + '.' + psio.get_default_namespace() + \
        'pcmsolver.' + str(uuid.uuid4())[:8]
    if os.path.exists(pcm_tmpdir) is False:
        os.mkdir(pcm_tmpdir)
    os.chdir(pcm_tmpdir)
    with open('pcmsolver.inp', 'w') as handle:
        handle.write(block)
    import pcmsolver
    pcmsolver.parse_pcm_input('pcmsolver.inp')
    os.chdir(curdir)


def filter_comments(string):
    """Remove from *string* any Python-style comments ('#' to end of line)."""

    filtered = []
    for line in string.splitlines():
        line = line.partition('#')[0]
        filtered.append(line.rstrip())
    return '\n'.join(filtered)


def basname(name):
    """Imitates BasisSet.make_filename() without the gbs extension"""
    return name.lower().replace('+', 'p').replace('*', 's').replace('(', '_').replace(')', '_').replace(',', '_')


def basis_helper(block, name='', key='BASIS', set_option=True):
    """For PsiAPI mode, forms a basis specification function from *block*
    and associates it with keyword *key* under handle *name*. Registers
    the basis spec with Psi4 so that it can be applied again to future
    molecules. For usage, see mints2, mints9, and cc54 test cases. Unless
    *set_option* is False, *name* will be set as current active *key*,
    equivalent to `set key name` or `set_option({key: name})`.

    """
    key = key.upper()
    name = ('anonymous' + str(uuid.uuid4())[:8]) if name == '' else name
    cleanbas = basname(name).replace('-', '')  # further remove hyphens so can be function name
    block = filter_comments(block)
    command_lines = re.split('\n', block)

    symbol_re = re.compile(r'^\s*assign\s+(?P<symbol>[A-Z]{1,3})\s+(?P<basis>[-+*\(\)\w]+)\s*$', re.IGNORECASE)
    label_re = re.compile(r'^\s*assign\s+(?P<label>(?P<symbol>[A-Z]{1,3})(?:(_\w+)|(\d+))?)\s+(?P<basis>[-+*\(\)\w]+)\s*$', re.IGNORECASE)
    all_re = re.compile(r'^\s*assign\s+(?P<basis>[-+*\(\)\w]+)\s*$', re.IGNORECASE)
    basislabel = re.compile(r'\s*\[\s*([-*\(\)\w]+)\s*\]\s*')

    def anon(mol, role):
        basstrings = {}

        # Start by looking for assign lines, and remove them
        leftover_lines = []
        assignments = False
        for line in command_lines:
            if symbol_re.match(line):
                m = symbol_re.match(line)
                mol.set_basis_by_symbol(m.group('symbol'), m.group('basis'), role=role)
                assignments = True

            elif label_re.match(line):
                m = label_re.match(line)
                mol.set_basis_by_label(m.group('label'), m.group('basis'), role=role)
                assignments = True

            elif all_re.match(line):
                m = all_re.match(line)
                mol.set_basis_all_atoms(m.group('basis'), role=role)
                assignments = True

            else:
                # Ignore blank lines and accumulate remainder
                if line and not line.isspace():
                    leftover_lines.append(line.strip())

        # Now look for regular basis set definitions
        basblock = list(filter(None, basislabel.split('\n'.join(leftover_lines))))
        if len(basblock) == 1:
            if not assignments:
                # case with no [basname] markers where whole block is contents of gbs file
                mol.set_basis_all_atoms(name, role=role)
                basstrings[basname(name)] = basblock[0]
            else:
                message = ("Conflicting basis set specification: assign lines present but shells have no [basname] label.""")
                raise TestComparisonError(message)
        else:
            # case with specs separated by [basname] markers
            for idx in range(0, len(basblock), 2):
                basstrings[basname(basblock[idx])] = basblock[idx + 1]

        return basstrings
    anon.__name__ = 'basisspec_psi4_yo__' + cleanbas
    qcdb.libmintsbasisset.basishorde[name.upper()] = anon
    if set_option:
        core.set_global_option(key, name)

core.OEProp.valid_methods = [
    'DIPOLE', 'QUADRUPOLE', 'MULLIKEN_CHARGES', 'LOWDIN_CHARGES', 'WIBERG_LOWDIN_INDICES',
    'MAYER_INDICES', 'MAYER_INDICES', 'MO_EXTENTS', 'GRID_FIELD', 'GRID_ESP', 'ESP_AT_NUCLEI',
    'NO_OCCUPATIONS'
]

## Option helpers

def py_psi_set_global_option_python(key, EXTERN):
    """
    This is a fairly hacky way to get around EXTERN issues. Effectively we are routing this option Python side through attributes until the general Options overhaul.
    """
    if (key != "EXTERN"):
        raise ValidationError("Options: set_global_option_python does not recognize keyword %s" % key)

    if EXTERN == None:
        core.EXTERN = None
        core.set_global_option("EXTERN", False)
    elif isinstance(EXTERN, core.ExternalPotential):
        # Well this is probably the worst hack I have done, thats saying something
        core.EXTERN = EXTERN
        core.set_global_option("EXTERN", True)
    else:
        raise ValidationError("Options: set_global_option_python can either be a NULL or External Potential object")


core.set_global_option_python = py_psi_set_global_option_python


