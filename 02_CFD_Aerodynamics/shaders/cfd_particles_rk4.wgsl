// ==============================================================================
// WebGPU Compute Shader: RK4 Streamline Advection Solver
// Project: PROJECT_07 - Boeing 777 Aerospace Engineering Suite
// Workgroup Size: 64 | Target Particles: 65,536 (1,024 Workgroups)
// ==============================================================================

struct Particle {
    pos : vec4<f32>,
    vel : vec4<f32>,
    color : vec4<f32>,
    lifetime : vec4<f32>,
};

struct SimulationParams {
    mach : f32,
    aoa_rad : f32,
    dt : f32,
    reynolds_mil : f32,
    domain_min : vec4<f32>,
    domain_max : vec4<f32>,
};

@group(0) @binding(0) var<storage, read_write> particles : array<Particle>;
@group(0) @binding(1) var<uniform> params : SimulationParams;

// Compressible flowfield velocity evaluation over Boeing 777 airframe
fn evaluate_velocity_field(p : vec3<f32>) -> vec3<f32> {
    let u_inf = params.mach * 296.4;
    let cos_a = cos(params.aoa_rad);
    let sin_a = sin(params.aoa_rad);
    var v = vec3<f32>(0.0, -u_inf * sin_a, u_inf * cos_a);

    // Fuselage cylinder deflection model (radius 3.1m, span -35 to +35)
    let r2 = p.x * p.x + p.y * p.y;
    let R_fuse = 3.1;
    if (r2 > 0.01 && r2 < 25.0 && p.z > -32.0 && p.z < 35.0) {
        let factor = (R_fuse * R_fuse) / r2;
        v.x = v.x + v.z * factor * (p.x / r2);
        v.y = v.y + v.z * factor * (p.y / r2);
    }

    // Wing circulation and upwash/downwash induction
    let y_span = abs(p.x);
    if (y_span < 32.4 && p.z > -5.0 && p.z < 15.0) {
        let sweep_z = y_span * tan(0.552); // 31.64 deg sweep
        let dist_le = p.z - sweep_z;
        if (dist_le > -2.0 && dist_le < 8.0) {
            let circulation = 450.0 * sqrt(max(0.0, 1.0 - (y_span / 32.4) * (y_span / 32.4)));
            let downwash = (circulation / (2.0 * 3.14159 * (dist_le * dist_le + p.y * p.y + 0.5))) * 0.12;
            v.y = v.y - downwash;
        }
    }

    return v;
}

@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) global_id : vec3<u32>) {
    let index = global_id.x;
    if (index >= arrayLength(&particles)) {
        return;
    }

    var p = particles[index];
    let pos0 = p.pos.xyz;
    let dt = params.dt;

    // 4th-Order Runge-Kutta (RK4) Particle Integration
    let k1 = evaluate_velocity_field(pos0);
    let k2 = evaluate_velocity_field(pos0 + 0.5 * dt * k1);
    let k3 = evaluate_velocity_field(pos0 + 0.5 * dt * k2);
    let k4 = evaluate_velocity_field(pos0 + dt * k3);

    let next_pos = pos0 + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4);
    let vel = (k1 + 2.0 * k2 + 2.0 * k3 + k4) / 6.0;
    let speed = length(vel);

    // Color mapping by Mach number (Jet colormap: Blue -> Green -> Red)
    let local_mach = speed / 296.4;
    var col = vec4<f32>(0.2, 0.4, 0.9, 0.8);
    if (local_mach > 0.84) {
        col = vec4<f32>(0.9, 0.2, 0.1, 0.9); // Supersonic recompression shock
    } else if (local_mach > 0.70) {
        col = vec4<f32>(0.2, 0.85, 0.3, 0.8); // Favorable acceleration
    }

    // Boundary recycling
    if (next_pos.z > 60.0 || next_pos.y < -20.0 || next_pos.y > 30.0 || abs(next_pos.x) > 45.0) {
        // Recycle upstream at nozzle or fuselage intake
        p.pos = vec4<f32>((f32(index % 100u) - 50.0) * 0.7, (f32((index / 100u) % 40u) - 20.0) * 0.4, -45.0, 1.0);
        p.vel = vec4<f32>(0.0, 0.0, params.mach * 296.4, 0.0);
        p.lifetime = vec4<f32>(0.0, 0.0, 0.0, 0.0);
    } else {
        p.pos = vec4<f32>(next_pos, 1.0);
        p.vel = vec4<f32>(vel, 0.0);
        p.color = col;
        p.lifetime.x = p.lifetime.x + dt;
    }

    particles[index] = p;
}
