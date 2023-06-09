# -*- coding: utf-8 -*-
"""A.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/15i41bT9-QRwRtpUepfLGGcFbtWg6CfnN
"""

import jax
jax.config.update("jax_enable_x64", True)
import jax.numpy as jnp
from jax.experimental import ode

!nvidia-smi
jax.devices()

"""# Problem setup

For single qubit, we integrate time-dependent Schrodinger euqation from $0$ to $T$, under the initial condition $ψ(0)= |g>$

$$ \frac{dψ}{dt} = -i H (t)ψ.$$ 

We'd like find an optimal control Hamiltonian so that the final evolution state $ψ(T)$ match a desired state, say, [0,1,1] state. 

Here $$H(t)= \sum_{i=1}^{n_{ctrl}} u_i(t) h_i ,$$
where $h_i$'s are time-independent driving Hamiltonian.

$u_i(t)$ are control field. We parametrize them as superpositions of Fourier series:

$$u_i(t) = \sum_{j=1}^{n_{basis}} u_{ij} \sin\left(\frac{\pi j t}{T}\right).$$ So, in the end, we try to find out suitiable $u_{ij}$'s to achieve our goal.

First, set up the target state and the Hamiltonian terms
"""

dim = 3 # Hilbert space dimension 
n_ctrl = 2 # number of contorl term
t_final = 0.5 # final control time (us)

Omega_ge = 10 #(MHz)
Omega_ef = 10 

psi_target = jnp.array([0,1,1])  #设置所要态！！
psi_target = psi_target/jnp.linalg.norm(psi_target)  #归一化

#control term
H_ctrl = []  #几个哈密顿量结合  
H_ge = jnp.array([[0, Omega_ge, 0], 
          [Omega_ge, 0, 0], 
          [0, 0, 0]]) #ge驱动
H_ef = jnp.array([[0, 0, 0], 
          [0, 0, Omega_ef], 
          [0, Omega_ef, 0]]) #ef驱动
H_ctrl.append(H_ge);H_ctrl.append(H_ef)

"""Here is our time-dependent Hamiltonian:"""

def buildH(t, params):  #用于试探的H(t) 输入时间和参数
  H = jnp.zeros((3,3,))
  params = params.reshape(n_ctrl, n_basis)  
  for i, H1 in enumerate(H_ctrl):  #enumerate() 函数用于将一个可遍历的数据对象(如列表、元组或字符串)组合为一个索引序列，同时列出数据和数据下标 (i, _)
    u = jnp.sum(jnp.sin((jnp.arange(n_basis)+1)*jnp.pi*t/t_final) * params[i])
    H = H + H1 * u 
  return H

"""# Objective function

So, our loss function will be the state infidelity 
$$\mathcal{L} = 1- |\mathrm{tr} (ρ_{ideal}ρ)| $$
"""

def statetoGellMann(state):
    phi=1/jnp.sqrt(state[0]*state[0].conjugate()+state[1]*state[1].conjugate()+state[2]*state[2].conjugate())*jnp.array([[state[0]],[state[1]],[state[2]]])  #一定要写成列向量的形式，写成行向量python也能算出结果但结果不对
    GellMann_1=jnp.array([[0,1,0],[1,0,0],[0,0,0]]).astype('complex')
    GellMann_2=jnp.array([[0,-1j,0],[1j,0,0],[0,0,0]])
    GellMann_3=jnp.array([[1,0,0],[0,-1,0],[0,0,0]]).astype('complex')
    GellMann_4=jnp.array([[0,0,1],[0,0,0],[1,0,0]]).astype('complex')
    GellMann_5=jnp.array([[0,0,-1j],[0,0,0],[1j,0,0]])
    GellMann_6=jnp.array([[0,0,0],[0,0,1],[0,1,0]]).astype('complex')
    GellMann_7=jnp.array([[0,0,0],[0,0,-1j],[0,1j,0]])
    GellMann_8=jnp.array([[1,0,0],[0,1,0],[0,0,-2]]).astype('complex')
    GellMann=[GellMann_1,GellMann_2,GellMann_3,GellMann_4,GellMann_5,GellMann_6,GellMann_7,1/jnp.sqrt(3)*GellMann_8]
    a=[phi.T.conjugate()@GellMann[i]@phi for i in range(len(GellMann))]
    return a

def GellManntorho(GellMann_rho): 
    GellMann_0=2/3*jnp.eye(3).astype('complex')
    GellMann_1=jnp.array([[0,1,0],[1,0,0],[0,0,0]]).astype('complex')
    GellMann_2=jnp.array([[0,-1j,0],[1j,0,0],[0,0,0]])
    GellMann_3=jnp.array([[1,0,0],[0,-1,0],[0,0,0]]).astype('complex')
    GellMann_4=jnp.array([[0,0,1],[0,0,0],[1,0,0]]).astype('complex')
    GellMann_5=jnp.array([[0,0,-1j],[0,0,0],[1j,0,0]])
    GellMann_6=jnp.array([[0,0,0],[0,0,1],[0,1,0]]).astype('complex')
    GellMann_7=jnp.array([[0,0,0],[0,0,-1j],[0,1j,0]])
    GellMann_8=jnp.array([[1,0,0],[0,1,0],[0,0,-2]]).astype('complex')
    GellMann=[GellMann_0,GellMann_1,GellMann_2,GellMann_3,GellMann_4,GellMann_5,GellMann_6,GellMann_7,1/jnp.sqrt(3)*GellMann_8]
    rho=jnp.zeros([3,3]).astype('complex')
    for i in range(len(GellMann_rho)):
        rho+=GellMann_rho[i]*GellMann[i]*3/2
    rho=1/3*rho
    return rho

def get_Statefedility3state(teststate,targetstate=psi_target):
    stateP=statetoGellMann(targetstate);stateP.insert(0,[[1]])  #目标
    T=statetoGellMann(teststate);T.insert(0,[[1]])  #探测
    P_rho=GellManntorho(jnp.array(T)) 
    P_rho_ideal=GellManntorho(jnp.array(stateP))
    return jnp.trace(jnp.dot(P_rho,P_rho_ideal)).real

def fidelity(psi_target, params):
  psit = ode.odeint(rhs, jnp.array([1,0,0])+1J*0, jnp.array([0.0, t_final]), params)  #odeint求解微分方程，第一个是微分方程函数，第二个是微分方程初值，第三个是微分的自变量

  return get_Statefedility3state(psit[-1],psi_target)

def loss(params):
  return 1.- fidelity(psi_target, params)

def rhs(psi, t, params):  #薛定谔方程
  H = buildH(t, params)
  return -1J*jnp.dot(H, psi)

"""# Optimization

For training, we can use quasi-Newton (BFGS) optimizer
"""

#initial parameters  
key = jax.random.PRNGKey(42)
key, subkey = jax.random.split(key)
n_basis = 10   #三角函数级数的阶数
params = jax.random.normal(subkey, (n_ctrl*n_basis, )) *0.01   

import jax.scipy.optimize
results = jax.scipy.optimize.minimize(loss, params, method='BFGS')

print (results.success, results.fun, fidelity(psi_target, results.x))

"""Whoa, that is almost perfect! 

Let's now plot the control field after optimization
"""

tlist = jnp.linspace(0, t_final, 51)
import matplotlib.pyplot as plt

d=['ge','ef']
fig = plt.figure(figsize=(6, 4), dpi=100)
for i in range(n_ctrl):
  coef_optimized = [jnp.sum(jnp.sin((jnp.arange(n_basis)+1)*jnp.pi*t/t_final) * results.x.reshape(n_ctrl, n_basis)[i] ) for t in tlist]
  plt.plot(tlist, coef_optimized, label=d[i])
plt.legend()
plt.xlabel('$t$')
plt.ylabel('control field')

"""Let's investigate hessian of the control. This is something you can easily do with `jax`. 

We simply compute seconder order gradient through the whole evolution and plot eigenvalues of the Hesssian matrix. Recall that at optimal we have 

$$ \mathcal{L} = \mathcal{L}(u^\ast) + \frac{1}{2}\frac{\partial ^2 \mathcal{L}}{\partial u_i \partial u_j} du_i du_j $$
"""

params = results.x
hess = jax.jacrev(jax.jacrev(loss))(params) # jax.hessian does fwd over rev

w, v = jnp.linalg.eigh(hess)

import matplotlib.pyplot as plt
plt.plot(w[::-1], 'ro')
plt.yscale('log')