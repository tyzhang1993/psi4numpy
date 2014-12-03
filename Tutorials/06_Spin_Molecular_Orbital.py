# A simple Psi 4 input script to compute MP3 utilizing antisymmetrized
# spin-orbitals
# Requirements scipy 0.13.0+ and numpy 1.7.2+
#
# From Szabo and Ostlund page 390
#
# Created by: Daniel G. A. Smith
# Date: 7/29/14
# License: GPL v3.0
#
import itertools as it
import time
import numpy as np
from scipy import linalg as SLA
np.set_printoptions(precision=5, linewidth=200, suppress=True)

# Memory for Psi4 in GB
memory 2 GB

# Memory for numpy in GB
numpy_memory = 2


molecule mol {
O
H 1 1.1
H 1 1.1 2 104
symmetry c1
}


set {
basis cc-pVDZ
scf_type pk
mp2_type conv
freeze_core false
e_convergence 1e-8
d_convergence 1e-8
}

# First compute RHF energy using Psi4
energy('RHF')

# Grab data from 
wfn = wavefunction()
# Coefficient Matrix
C = np.array(wfn.Ca())
# Double occupied orbitals
ndocc = wfn.doccpi()[0]
# Number of molecular orbitals
nmo = wfn.nmo()
# SCF energy
SCF_E = wfn.energy()
# Orbital energies
eps = wfn.epsilon_a()
eps = np.array([eps.get(x) for x in range(C.shape[0])])


# Compute size of SO-ERI tensor in GB
ERI_Size = (nmo**4)*(2**4)*8.0 / 1E9
print "\nSize of the SO ERI tensor will be %4.2f GB." % ERI_Size
memory_footprint = ERI_Size*2.2
if memory_footprint > numpy_memory:
    clean()
    raise Exception("Estimated memory utilization (%4.2f GB) exceeds numpy_memory limit of %4.2f GB." % (memory_footprint, numpy_memory))

# Integral generation from Psi4's MintsHelper
t = time.time()
mints = MintsHelper()
I = np.array(mints.ao_eri())
I = I.reshape(nmo, nmo, nmo, nmo)

print '\nTotal time taken for ERI integrals: %.3f seconds.\n' % (time.time()-t)


#Make spin-orbital MO
t=time.time()
print 'Starting AO -> spin-orbital MO transformation...'
nso = nmo * 2

MO = np.einsum('rJ,pqrs->pqJs', C, I)
MO = np.einsum('pI,pqJs->IqJs', C, MO)
MO = np.einsum('sB,IqJs->IqJB', C, MO)
MO = np.einsum('qA,IqJB->IAJB', C, MO)

# Tile MO array so that we have alternating alpha/beta spin orbitals
MO = np.repeat(MO, 2, axis=0)
MO = np.repeat(MO, 2, axis=1)
MO = np.repeat(MO, 2, axis=2)
MO = np.repeat(MO, 2, axis=3)

# Build spin mask
spin_ind = np.arange(nso, dtype=np.int) % 2
spin_mask = (spin_ind.reshape(-1, 1, 1, 1) == spin_ind.reshape(-1, 1, 1))
spin_mask = spin_mask * (spin_ind.reshape(-1, 1) == spin_ind)

# compute antisymmetrized MO integrals
MO *= spin_mask
MO = MO - MO.swapaxes(1, 3)
MO = MO.swapaxes(1, 2)
print '..finished transformation in %.3f seconds.\n' % (time.time()-t)


nph = NumpyHelper()
MO = np.array(nph.mo_spin_eri())


# Update nocc and nvirt
nocc = ndocc * 2
nvirt = MO.shape[0] - nocc

# Build epsilon tensor
eps = np.repeat(eps, 2)
eocc = eps[:nocc]
evirt = eps[nocc:]
epsilon = 1/(eocc.reshape(-1, 1, 1, 1) + eocc.reshape(-1, 1, 1) - evirt.reshape(-1, 1) - evirt)

# Create occupied and virtual slices
o = slice(0, nocc)
v = slice(nocc, MO.shape[0])

MP2corr_E = 0.25 * np.einsum('abrs,rsab,abrs', MO[o, o, v, v], MO[v, v, o, o], epsilon)


MP2total_E = SCF_E + MP2corr_E
print 'MP2 correlation energy:      %16.10f' % MP2corr_E
print 'MP2 total energy:            %16.10f' % MP2total_E

eqn1 = 0.125 * np.einsum('abrs,cdab,rscd,abrs,cdrs->', MO[o, o, v, v], MO[o, o, o, o], MO[v, v, o, o], epsilon, epsilon)
eqn2 = 0.125 * np.einsum('abrs,rstu,tuab,abrs,abtu', MO[o, o, v, v], MO[v, v, v, v], MO[v, v, o, o], epsilon, epsilon)
eqn3 = np.einsum('abrs,cstb,rtac,absr,acrt', MO[o, o, v, v], MO[o, v, v, o], MO[v, v, o, o], epsilon, epsilon)

MP3corr_E = eqn1 + eqn2 + eqn3
MP3total_E = MP2total_E + MP3corr_E
print '\nMP3 correlation energy:      %16.10f' % MP3corr_E
print 'MP3 total energy:            %16.10f' % MP3total_E
compare_values(energy('MP3'), MP3total_E, 6, 'MP3 Energy')



