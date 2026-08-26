# plan outline for ramping

to add ramping I want the following: 
ramping cost should be added to the objective function
four additional constraints to be added: 
$ V_{up} \geq g(p,t)-g(p,t-1)\leq R_{up}(p)$
$ V_{dwn} \geq g(p,t-1)-g(p,t)\leq R_{dwn}(p)$
$V_{up} \geq 0$
$V_{dwn} \geq 0$

$V_{up} and V_{dwn}$ are the ramp up and down speed respectively
g is generation

to be added to objective function:
$\sum_{t,p} R_{upcost} \times V_{up}(t,p) = \sum_{t,p} R_{dwncost} \times V_{dwn}(t,p)$
where the ramp up and down cost $R_{upcost}$ and $R_{dwncost}$ is based on the ramping efficiency for that plant and fuel, used instead of the efficiency at non ramping times.
These should be calculateable from the plants.csv and fuel.csv files

These equations should be added to the readme file along with the other constraints and the rest of the objective function
