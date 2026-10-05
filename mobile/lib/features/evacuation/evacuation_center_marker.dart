import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../app/theme/app_colors.dart';
import '../map/flood_map_palette.dart';

/// Three gentle, finite decorative beats. This never requests location or data.
double evacuationPulseStrength(double progress) {
  if (progress <= 0 || progress >= 1) return 0;
  final wave = math.sin(progress * math.pi * 3);
  return wave * wave;
}

/// Shared code-drawn shelter badge for OSM and native Mapbox style images.
/// A building symbol, not a medical cross, warning, or facility-open indicator.
void paintEvacuationShelter(Canvas canvas, Rect bounds, Color accent) {
  canvas.save();
  canvas.translate(bounds.left, bounds.top);
  canvas.scale(bounds.width / 48, bounds.height / 48);
  final badge = RRect.fromRectAndRadius(
    const Rect.fromLTWH(3, 3, 42, 42),
    const Radius.circular(10),
  );
  canvas.drawRRect(badge, Paint()..color = Colors.white);
  canvas.drawRRect(
    badge,
    Paint()
      ..color = accent
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.5,
  );
  final roof = Path()
    ..moveTo(10, 22)
    ..lineTo(24, 11)
    ..lineTo(38, 22);
  canvas.drawPath(
    roof,
    Paint()
      ..color = accent
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round
      ..strokeWidth = 3,
  );
  canvas.drawRRect(
    RRect.fromRectAndRadius(
      const Rect.fromLTWH(13, 21, 22, 16),
      const Radius.circular(2),
    ),
    Paint()..color = accent,
  );
  canvas.drawRect(
    const Rect.fromLTWH(21, 28, 6, 9),
    Paint()..color = Colors.white,
  );
  for (final left in [16.0, 29.0]) {
    canvas.drawRect(
      Rect.fromLTWH(left, 25, 3, 4),
      Paint()..color = Colors.white,
    );
  }
  canvas.restore();
}

class EvacuationCenterMarker extends StatefulWidget {
  const EvacuationCenterMarker({
    required this.name,
    required this.isNearest,
    required this.isSelected,
    required this.isDemonstration,
    this.onTap,
    super.key,
  });

  final String name;
  final bool isNearest;
  final bool isSelected;
  final bool isDemonstration;
  final VoidCallback? onTap;

  @override
  State<EvacuationCenterMarker> createState() => _EvacuationCenterMarkerState();
}

class _EvacuationCenterMarkerState extends State<EvacuationCenterMarker>
    with SingleTickerProviderStateMixin, WidgetsBindingObserver {
  late final AnimationController _pulse = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 3600),
  );
  bool _motionEnabled = false;
  bool _hasPlayed = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _syncMotion();
  }

  @override
  void didUpdateWidget(covariant EvacuationCenterMarker oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!oldWidget.isNearest && widget.isNearest) _hasPlayed = false;
    _syncMotion();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) => _syncMotion();

  void _syncMotion() {
    final lifecycle = WidgetsBinding.instance.lifecycleState;
    _motionEnabled =
        widget.isNearest &&
        TickerMode.valuesOf(context).enabled &&
        !MediaQuery.disableAnimationsOf(context) &&
        (lifecycle == null || lifecycle == AppLifecycleState.resumed);
    if (!_motionEnabled) {
      _pulse.stop();
      _pulse.value = 1;
      return;
    }
    if (!_hasPlayed) {
      _hasPlayed = true;
      _pulse.forward(from: 0);
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _pulse.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final status = widget.isDemonstration
        ? 'Local test—not a real facility'
        : 'Verified center information; availability not confirmed';
    final label = [
      widget.name,
      if (widget.isNearest) 'Nearest by approximate straight-line distance',
      status,
    ].join('. ');
    return Tooltip(
      message: label,
      excludeFromSemantics: true,
      child: Semantics(
        button: widget.onTap != null,
        selected: widget.isSelected,
        label: label,
        child: GestureDetector(
          onTap: widget.onTap,
          behavior: HitTestBehavior.opaque,
          child: AnimatedBuilder(
            animation: _pulse,
            builder: (context, _) => CustomPaint(
              key: const Key('evacuation-shelter-icon'),
              painter: _EvacuationMarkerPainter(
                isNearest: widget.isNearest,
                isSelected: widget.isSelected,
                isDemonstration: widget.isDemonstration,
                strength: _motionEnabled
                    ? evacuationPulseStrength(_pulse.value)
                    : 0,
              ),
              child: const SizedBox(width: 56, height: 56),
            ),
          ),
        ),
      ),
    );
  }
}

class _EvacuationMarkerPainter extends CustomPainter {
  const _EvacuationMarkerPainter({
    required this.isNearest,
    required this.isSelected,
    required this.isDemonstration,
    required this.strength,
  });

  final bool isNearest;
  final bool isSelected;
  final bool isDemonstration;
  final double strength;

  @override
  void paint(Canvas canvas, Size size) {
    final center = size.center(Offset.zero);
    if (isNearest || isSelected) {
      canvas.drawCircle(
        center,
        size.shortestSide * (0.42 + strength * 0.075),
        Paint()..color = FloodMapPalette.center.withValues(alpha: 0.16),
      );
      canvas.drawCircle(
        center,
        size.shortestSide * (0.42 + strength * 0.075),
        Paint()
          ..color = FloodMapPalette.center.withValues(alpha: 0.65)
          ..style = PaintingStyle.stroke
          ..strokeWidth = isSelected ? 3 : 2,
      );
    }
    paintEvacuationShelter(
      canvas,
      Rect.fromCenter(center: center, width: 44, height: 44),
      FloodMapPalette.center,
    );
    if (isNearest) {
      final badgeCenter = center + const Offset(15, -15);
      canvas.drawCircle(
        badgeCenter,
        8,
        Paint()..color = FloodMapPalette.center,
      );
      final text = TextPainter(
        text: const TextSpan(
          text: '1',
          style: TextStyle(
            color: Colors.white,
            fontSize: 11,
            fontWeight: FontWeight.w800,
          ),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      text.paint(canvas, badgeCenter - Offset(text.width / 2, text.height / 2));
      text.dispose();
    }
    if (isDemonstration) {
      final badgeCenter = center + const Offset(0, 22);
      canvas.drawRRect(
        RRect.fromRectAndRadius(
          Rect.fromCenter(center: badgeCenter, width: 30, height: 12),
          const Radius.circular(3),
        ),
        Paint()..color = AppColors.warningSurface,
      );
      final text = TextPainter(
        text: const TextSpan(
          text: 'TEST',
          style: TextStyle(
            color: AppColors.bodyText,
            fontSize: 9,
            fontWeight: FontWeight.w800,
          ),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      text.paint(canvas, badgeCenter - Offset(text.width / 2, text.height / 2));
      text.dispose();
    }
  }

  @override
  bool shouldRepaint(_EvacuationMarkerPainter oldDelegate) =>
      oldDelegate.isNearest != isNearest ||
      oldDelegate.isSelected != isSelected ||
      oldDelegate.isDemonstration != isDemonstration ||
      oldDelegate.strength != strength;
}
