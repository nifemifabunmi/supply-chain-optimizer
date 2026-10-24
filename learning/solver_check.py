import pulp

prob = pulp.LpProblem("check", pulp.LpMinimize)
x = prob.add_variable("x", lowBound=0)
y = prob.add_variable("y", lowBound=0)
prob += 2 * x + 3 * y
prob += x + y >= 10
prob += x <= 6
stats = prob.solve(pulp.COIN_CMD(msg=False))
print(stats.status_str, pulp.value(prob.objective), x.value(), y.value())