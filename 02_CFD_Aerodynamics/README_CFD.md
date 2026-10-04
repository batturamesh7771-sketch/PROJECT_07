# CFD Aerodynamics Technical Specification: Boeing 777 Suite

## 1. Governing Equations & Turbulence Closure
The simulation suite implements the 3D Reynolds-Averaged Navier-Stokes (RANS) equations with Menter's Shear Stress Transport ($k$-$\omega$ SST) two-equation eddy-viscosity model:

$$\frac{\partial \rho}{\partial t} + \nabla \cdot (\rho \mathbf{u}) = 0$$

$$\frac{\partial (\rho \mathbf{u})}{\partial t} + \nabla \cdot (\rho \mathbf{u} \otimes \mathbf{u}) = -\nabla p + \nabla \cdot (\boldsymbol{\tau} + \boldsymbol{\tau}^R) + \mathbf{S}_M$$

## 2. Flight Reference Conditions
* **Cruise Mach:** $M_\infty = 0.84$
* **Altitude:** 35,000 ft (FL350, ISA standard atmosphere)
* **Reynolds Number:** $Re_{MAC} = 45.2 \times 10^6$ based on mean aerodynamic chord ($7.42\text{ m}$)
* **Wing Area:** $S_{ref} = 436.8\text{ m}^2$ (4,702 sq ft)
* **Aspect Ratio:** $AR = 9.61$
* **Sweep Angle:** $\Lambda_{c/4} = 31.64^\circ$

## 3. Transonic Shock Recompression & Drag Divergence
The supercritical wing profile delays the drag divergence Mach number to $M_{div} = 0.865$. Supercritical suction plateau maintains favorable pressure gradient over 55% chord before gentle recompression.
