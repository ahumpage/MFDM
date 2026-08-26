# My first Dispatch Model

This repo provides the power market model and dashboard for the my first dispatch model onboarding.
Its purpose is to create a python PuLP linear optimisation model which determines the cheapest way to dispatch a set of power plants to meet electricity demand over a set of time periods.

It is made up of the following:

## Sets
Power plants (P)
Time (T)
Fuel

## Parameters
Psupp(P,T) - how much each plant can supply MWh
Pcost(P,T) - Cost to produce 1 MWh of electricity $/MWh
Efficiency(P) - efficiency MWh/MWhTh

Pcost(P,T) = (fuel cost)/(efficiency) +VOM

## Decision variable
Which powerplants to dispatch

## Objective function
Minimise the production cost of electricity while meeting demand

$Minimise (total cost) = \sum_{p,t} MC(p) \times g(p,t) \\ + \sum_{t} LoL_{cost} \times LoL(t) \\ + \sum_{t} Spill_{cost} \times spill(t) \\ + \sum_{t,p} R_{upcost} \times V_{up}(t,p) + \sum_{t,p} R_{dwncost} \times V_{dwn}(t,p)$

## Constraints
Demand = supply
Each plant has a capacity
Pcostmax(T) = Pcost(P,T) minimimum required to meet demand
